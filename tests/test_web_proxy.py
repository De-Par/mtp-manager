from dataclasses import replace
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import Mock, patch

from controller import AppController
from errors import ServiceError, SourceBuildRequiredError, ValidationError
from i18n import Translator
from infra.storage import JsonStorage
from infra.telemt import supports_web
from models.secret import SecretRecord, UserRecord
from models.settings import AppSettings
from paths import ProjectPaths
from services.export_service import ExportService
from services.inventory_service import InventoryService
from services.proxy_runtime_service import ProxyRuntimeService
from services.settings_service import SettingsService
from services.source_service import SourceService
from services.web_proxy_service import WebProxyService

SECRET = "000102030405060708090a0b0c0d0e0f"


def web_settings(**changes):
    return replace(AppSettings(proxy_mode="web", web_domain="proxy.example.com", web_public_ip="8.8.8.8", web_frontend="external"), **changes)


class SettingsTests(unittest.TestCase):
    def test_old_settings_keep_native_mode_and_round_trip(self):
        settings = AppSettings.from_dict({"mt_port": 8443, "fake_tls_domain": "example.com", "ui_lang": "ru"})
        self.assertEqual(settings.proxy_mode, "mtproto")
        self.assertEqual(settings.public_ports, {8443})
        self.assertEqual(AppSettings.from_dict(settings.to_dict()), settings)
        settings = web_settings(proxy_mode="both", mt_port=8443, web_base_path="Telegram/web-1")
        self.assertEqual(AppSettings.from_dict(settings.to_dict()), settings)
        self.assertEqual(settings.public_ports, {443, 8443})

    def test_invalid_web_endpoints_and_ports_are_rejected(self):
        cases = [
            {"proxy_mode": "socks"}, {"web_domain": "8.8.8.8"}, {"web_domain": "UPPER.example.com"},
            {"web_domain": "https://proxy.example.com"}, {"web_domain": "proxy.example.com:443"},
            {"web_public_ip": "proxy.example.com"}, {"web_public_ip": "127.0.0.1"},
            {"web_public_ip": "10.0.0.1"}, {"web_public_ip": "0.0.0.0"},
            {"web_port": 0}, {"web_port": 65536}, {"web_port": 443}, {"web_port": 8888},
            {"stats_port": 443}, {"proxy_mode": "both"},
            {"proxy_mode": "both", "mt_port": 18080}, {"proxy_mode": "both", "mt_port": 8888},
            {"web_base_path": "/telegram/web"}, {"web_base_path": "telegram/web/"},
            {"web_base_path": "telegram//web"}, {"web_base_path": "telegram/../web"},
            {"web_base_path": "web?token=x"}, {"web_base_path": "x" * 129},
            {"web_base_path": "путь"}, {"web_decoy_dir": "relative/site"},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                web_settings(**changes).validate()

    def test_ipv6_and_exact_case_sensitive_base(self):
        settings = web_settings(web_public_ip="2606:4700:4700::1111", web_base_path="Telegram/Web")
        settings.validate()
        self.assertEqual(settings.web_public_addr, "[2606:4700:4700::1111]:443")
        self.assertEqual(settings.web_endpoint, "https://proxy.example.com/Telegram/Web/")


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.paths = ProjectPaths(root=root, mt_dir=root / "telemt", conf_dir=root / "conf", data_dir=root / "data")
        self.storage = JsonStorage()
        self.inventory = InventoryService(self.storage, self.paths)
        self.inventory.add_user("alice")
        self.secret = self.inventory.add_secret("alice", raw_secret=SECRET)
        self.runtime = ProxyRuntimeService(self.storage, self.inventory, self.paths)
        self.paths.binary_file.parent.mkdir(parents=True)
        self.paths.binary_file.write_bytes(b"test binary tg://webproxy?server=")

    def config(self, settings):
        return tomllib.loads(self.runtime.rebuild_runtime_config(settings))

    def test_native_config_and_exports_remain_compatible(self):
        settings = AppSettings(fake_tls_domain="example.com")
        config = self.config(settings)
        self.assertNotIn("web", config)
        self.assertEqual(config["server"]["listeners"], [{"ip": "0.0.0.0", "port": 443}])
        self.assertTrue(config["general"]["modes"]["tls"])
        bundle = ExportService().build_bundle("8.8.8.8", settings, self.inventory.get_user("alice"), self.secret)
        self.assertEqual(bundle.links.tg_padded, f"tg://proxy?server=8.8.8.8&port=443&secret=dd{SECRET}")
        self.assertIsNone(bundle.links.tg_web_raw)

    def test_web_only_config_is_private_and_creates_frontend_examples(self):
        settings = web_settings(web_public_ip="2606:4700:4700::1111", web_base_path="telegram/web")
        config = self.config(settings)
        listener, = config["server"]["listeners"]
        self.assertEqual((listener["ip"], listener["port"], listener["transport"]), ("127.0.0.1", 18080, "web"))
        self.assertFalse(listener["proxy_protocol"])
        self.assertEqual(listener["web_trusted_proxy_cidrs"], ["127.0.0.1/32"])
        self.assertEqual(config["web"]["carrier"], "https")
        self.assertFalse(config["general"]["modes"]["tls"])
        vhost, = config["web"]["vhosts"]
        self.assertEqual(vhost["public_addr"], "[2606:4700:4700::1111]:443")
        self.assertEqual({p["secret_mode"] for p in vhost["profiles"]}, {"plain", "dd"})
        self.assertTrue(all(p["user"] in config["access"]["users"] for p in vhost["profiles"]))
        self.assertTrue((self.paths.web_decoy_dir / "index.html").is_file())
        nginx = self.paths.web_nginx_file.read_text()
        self.assertIn("location = /telegram/web", nginx)
        self.assertIn("location ^~ /telegram/web/", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:18080;", nginx)
        self.assertIn("proxy_set_header X-Forwarded-For $remote_addr;", nginx)
        self.assertIn("proxy_next_upstream off;", nginx)
        self.assertNotIn("rewrite", nginx)
        caddy = self.paths.web_caddy_file.read_text()
        self.assertIn("@web path /telegram/web /telegram/web/*", caddy)
        self.assertNotIn("handle_path", caddy)

    def test_secret_lifecycle_updates_both_transports(self):
        settings = web_settings(proxy_mode="both", mt_port=8443, fake_tls_domain="example.com")
        systemd = Mock()
        systemd.is_installed.return_value = True
        self.runtime.reconcile(settings, systemd)
        self.assertEqual(len(self.config(settings)["server"]["listeners"]), 2)
        rotated = self.inventory.rotate_secret(self.secret.id)
        self.runtime.reconcile(settings, systemd)
        config = tomllib.loads(self.paths.telemt_config_file.read_text())
        self.assertEqual(list(config["access"]["users"].values()), [rotated.raw_secret])
        self.assertNotIn(SECRET, self.paths.telemt_config_file.read_text())
        self.inventory.set_user_enabled("alice", False)
        self.runtime.reconcile(settings, systemd)
        config = tomllib.loads(self.paths.telemt_config_file.read_text())
        self.assertEqual(config["access"]["users"], {})
        self.assertFalse(config["web"]["enabled"])
        self.assertNotIn("profiles", config["web"]["vhosts"][0])
        systemd.stop.assert_called_once()
        self.inventory.set_user_enabled("alice", True)
        self.inventory.set_secret_enabled(self.secret.id, False)
        self.assertEqual(self.config(settings)["access"]["users"], {})
        self.inventory.set_secret_enabled(self.secret.id, True)
        self.assertEqual(len(self.config(settings)["web"]["vhosts"][0]["profiles"]), 2)
        self.inventory.delete_secret(self.secret.id)
        self.assertFalse(self.config(settings)["web"]["enabled"])

    def test_long_unicode_username_keeps_access_profile_binding(self):
        self.inventory.add_user("пользователь" * 8)
        self.inventory.add_secret("пользователь" * 8)
        config = self.config(web_settings())
        for profile in config["web"]["vhosts"][0]["profiles"]:
            self.assertLessEqual(len(profile["user"].encode()), 64)
            self.assertIn(profile["user"], config["access"]["users"])

    def test_custom_decoy_is_preserved_and_invalid_decoy_does_not_save(self):
        directory = Path(self.temp.name) / "site"
        directory.mkdir()
        (directory / "index.html").write_text("Custom website")
        self.config(web_settings(web_decoy_dir=str(directory)))
        self.assertEqual((directory / "index.html").read_text(), "Custom website")
        settings = SettingsService(self.storage, self.paths, self.runtime, Mock(), Mock())
        settings.save(AppSettings())
        with self.assertRaises(ValidationError):
            settings.update(**web_settings(web_decoy_dir=str(directory / "missing")).to_dict())
        self.assertEqual(settings.load().proxy_mode, "mtproto")

    def test_unsupported_binary_rejected_before_settings_and_firewall_changes(self):
        self.paths.binary_file.write_bytes(b"old telemt")
        firewall = Mock()
        settings = SettingsService(self.storage, self.paths, self.runtime, Mock(), firewall)
        settings.save(AppSettings())
        with self.assertRaises(ServiceError):
            settings.update(**web_settings().to_dict())
        self.assertEqual(settings.load().proxy_mode, "mtproto")
        firewall.allow_tcp.assert_not_called()

    def test_firewall_preserves_https_across_combined_port_changes(self):
        firewall = Mock()
        settings = SettingsService(self.storage, self.paths, firewall=firewall)
        settings.save(AppSettings())
        settings.update(**web_settings(proxy_mode="both", mt_port=8443).to_dict())
        firewall.allow_tcp.assert_any_call(8443)
        firewall.delete_allow_tcp.assert_not_called()
        firewall.reset_mock()
        settings.update(mt_port=9443)
        firewall.allow_tcp.assert_any_call(9443)
        firewall.delete_allow_tcp.assert_called_once_with(8443)
        firewall.reset_mock()
        settings.update(proxy_mode="web")
        firewall.delete_allow_tcp.assert_called_once_with(9443)
        firewall.allow_tcp.assert_any_call(22)
        self.assertNotIn(unittest.mock.call(18080), firewall.allow_tcp.call_args_list)


class LinkTests(unittest.TestCase):
    def test_upstream_root_and_path_test_vectors(self):
        export = ExportService()
        self.assertEqual(export.web_link("proxy.example.com", SECRET), f"tg://webproxy?server=proxy.example.com&secret={SECRET}")
        self.assertEqual(export.web_link("proxy.example.com", "dd" + SECRET), f"tg://webproxy?server=proxy.example.com&secret=dd{SECRET}")
        # Exact vectors from Telemt's format_web_proxy_link tests.
        self.assertEqual(export.web_link("proxy.example.com", SECRET, "dobry-cola/super_app"),
                         "tg://webproxy?server=proxy.example.com%2Fdobry-cola%2Fsuper_app&secret=cAABAgMEBQYHCAkKCwwNDg8")
        self.assertEqual(export.web_link("proxy.example.com", "dd" + SECRET, "dobry-cola/super_app"),
                         "tg://webproxy?server=proxy.example.com%2Fdobry-cola%2Fsuper_app&secret=cN0AAQIDBAUGBwgJCgsMDQ4P")

    def test_web_only_export_omits_native_and_ee_links(self):
        export = ExportService()
        bundle = export.build_bundle("unavailable", web_settings(fake_tls_domain="example.com"), UserRecord("alice"), SecretRecord(1, SECRET))
        text = export.render_bundles([bundle])
        self.assertIn("WEB DD: tg://webproxy?server=proxy.example.com&secret=dd", text)
        self.assertNotIn("tg://proxy", text)
        self.assertNotIn("EE:", text)
        self.assertEqual(bundle.port, 443)
        self.assertEqual(bundle.host, "proxy.example.com")


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = ProjectPaths(root=Path(self.temp.name), mt_dir=Path(self.temp.name) / "telemt")
        self.source = SourceService(Mock(), self.paths)

    def test_latest_without_web_requests_build_and_then_builds_main(self):
        with patch.object(self.source, "_install_release_binary", side_effect=lambda: self.paths.binary_file.write_bytes(b"old")), \
             patch.object(self.source, "_build_from_source", side_effect=lambda ref: self.paths.binary_file.write_bytes(b"tg://webproxy?server=")) as build:
            with self.assertRaises(SourceBuildRequiredError):
                self.source.install("update", allow_build=False, require_web=True)
            build.assert_not_called()
            self.source.install("update", allow_build=True, require_web=True)
            build.assert_called_once_with("main")

    def test_pinned_incompatible_release_is_rejected(self):
        with patch.object(self.source, "_install_release_binary", side_effect=lambda ref: self.paths.binary_file.write_bytes(b"old")):
            with self.assertRaises(ServiceError):
                self.source.install("update", "3.0.0", require_web=True)

    def test_reuse_capable_binary_and_marker_crossing_read_boundary(self):
        self.paths.binary_file.parent.mkdir(parents=True)
        self.paths.binary_file.write_bytes(b"x" * (1024 * 1024 - 10) + b"tg://webproxy?server=")
        self.assertTrue(supports_web(self.paths.binary_file))
        with patch.object(self.source, "_install_release_binary") as download:
            self.source.install("reuse", require_web=True)
            download.assert_not_called()
