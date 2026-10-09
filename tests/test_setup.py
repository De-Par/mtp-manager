from dataclasses import replace
import hashlib
import io
from pathlib import Path
import socket
import ssl
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from controller import AppController
from errors import ServiceError, ValidationError
from i18n import Translator
from infra.rust import ensure_cargo
from infra.distro import DistroInfo
from infra.packages import PackageManager
from infra.shell import CommandResult
from infra.storage import JsonStorage
from models.health import HealthCheck, HealthReport
from models.settings import AppSettings
from paths import ProjectPaths
from services.export_service import ExportService
from services.https_service import HttpsService
from services.install_service import InstallService, SetupOptions
from services.inventory_service import InventoryService
from services.proxy_runtime_service import ProxyRuntimeService
from services.settings_service import SettingsService
from services.systemd_service import SystemdService

WAIT_RUNTIME_READY = InstallService.wait_runtime_ready

DNS_ANSWER = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]


class SetupFixture:
    def make_fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.paths = ProjectPaths(root=root, mt_dir=root / "opt/telemt", conf_dir=root / "etc/mtp-manager",
            data_dir=root / "var/lib/mtp-manager", self_install_path=root / "bin/mtp-manager",
            service_file=root / "systemd/telemt.service", refresh_service_file=root / "systemd/refresh.service",
            refresh_timer_file=root / "systemd/refresh.timer", cleanup_service_file=root / "systemd/cleanup.service",
            cleanup_timer_file=root / "systemd/cleanup.timer")
        self.storage = JsonStorage()
        self.inventory = InventoryService(self.storage, self.paths)
        self.manager = Mock()
        self.manager.is_active.return_value = "active"
        self.systemd = SystemdService(self.manager, self.storage, self.paths)
        self.shell = Mock()
        self.shell.run.return_value = CommandResult([], 0, "", "")
        self.https = HttpsService(self.shell, self.manager, self.storage, self.paths)
        self.runtime = ProxyRuntimeService(self.storage, self.inventory, self.paths)
        self.settings = SettingsService(self.storage, self.paths, self.runtime, self.systemd, Mock(), self.https)
        self.source = Mock()
        def install(*args, **kwargs):
            self.paths.binary_file.parent.mkdir(parents=True, exist_ok=True)
            self.paths.binary_file.write_bytes(b"tg://webproxy?server=")
            return self.paths.binary_file
        self.source.install.side_effect = install
        self.packages = Mock()
        self.packages.package_set.runtime = ("ca-certificates",)
        self.packages.package_set.build = ("cargo", "gcc")
        self.installer = InstallService(self.shell, Mock(), self.packages, Mock(), self.source,
                                        self.runtime, self.systemd, Mock(), self.https)
        diagnostics = Mock()
        diagnostics.build_report.return_value = HealthReport([
            HealthCheck("public_ip", "public_ip", "8.8.8.8"),
            HealthCheck("service_status", "service_status", "active"),
            HealthCheck("telemt_version", "telemt_version", "test"),
        ])
        self.controller = AppController(Translator("ru"), self.settings, self.inventory, ExportService(), diagnostics,
            self.installer, Mock(), self.runtime, self.systemd, self.paths, self.https)
        self.web = AppSettings(proxy_mode="both", mt_port=8443, web_domain="proxy.example.com", web_public_ip="8.8.8.8")

    def mock_host(self):
        self.host_patches = []
        for target, kwargs in (
            ("services.install_service.os.geteuid", {"return_value": 0}),
            ("services.https_service.socket.getaddrinfo", {"return_value": DNS_ANSWER}),
            ("services.https_service.HttpsService.check_ports_available", {}),
            ("services.https_service.HttpsService.probe", {}),
            ("services.https_service.HttpsService.install_binary", {"side_effect": self.install_caddy}),
            ("services.install_service.InstallService.wait_runtime_ready", {}),
            ("services.install_service.InstallService.check_runtime_ports", {}),
        ):
            item = patch(target, **kwargs)
            self.host_patches.append(item.start())
            self.addCleanup(item.stop)

    def install_caddy(self):
        self.paths.caddy_binary.parent.mkdir(parents=True, exist_ok=True)
        self.paths.caddy_binary.write_bytes(b"test caddy")


class SetupTests(SetupFixture, unittest.TestCase):
    def setUp(self):
        self.make_fixture()
        self.mock_host()

    def test_first_setup_provisions_https_secret_firewall_and_boot_services(self):
        progress = Mock()
        result = self.controller.setup_from_form(self.web, initial_user="first", progress=progress)
        self.assertEqual(self.inventory.enabled_secret_count(), 1)
        self.assertTrue(self.paths.web_service_file.is_file())
        self.assertIn("admin off", self.paths.caddy_config_file.read_text())
        self.assertIn("tg://webproxy", result)
        self.assertIn("tg://proxy", result)
        self.assertEqual(self.storage.load_json(self.paths.web_state_file, {})["status"], "ready")
        self.manager.enable.assert_any_call("telemt.service", start=False)
        self.manager.enable.assert_any_call("mtp-manager-web.service", start=False)
        self.installer.firewall.allow_tcp.assert_has_calls([call(22), call(80), call(443), call(8443)])
        self.manager.start.assert_any_call("telemt.service")
        self.manager.restart.assert_called_once_with("mtp-manager-web.service")
        progress.assert_any_call("setup_https")
        # An idempotent retry reuses the first secret and certificate directory.
        raw = self.inventory.get_user("first").secrets[0].raw_secret
        self.controller.setup_from_form(self.web, initial_user="second")
        self.assertEqual(self.inventory.enabled_secret_count(), 1)
        self.assertEqual(self.inventory.get_user("first").secrets[0].raw_secret, raw)

    def test_dns_failure_does_not_save_settings_create_user_or_install(self):
        with patch("services.https_service.socket.getaddrinfo", return_value=[]):
            with self.assertRaisesRegex(ValidationError, "web_dns_mismatch"):
                self.controller.setup_from_form(self.web)
        self.assertEqual(self.settings.load().proxy_mode, "mtproto")
        self.assertEqual(self.inventory.load_users(), [])
        self.source.install.assert_not_called()
        self.manager.start.assert_not_called()

    def test_tls_failure_is_reported_as_pending_and_never_ready(self):
        with patch.object(self.https, "probe", side_effect=ssl.SSLError("pending")):
            with self.assertRaisesRegex(ServiceError, "web_https_pending"):
                self.https.wait_ready(self.web, timeout=0)
        self.assertEqual(self.storage.load_json(self.paths.web_state_file, {})["status"], "pending")

    def test_native_setup_creates_first_secret_without_caddy(self):
        self.controller.setup_from_form(AppSettings(), initial_user="native")
        self.assertEqual(self.inventory.enabled_secret_count(), 1)
        self.assertFalse(self.paths.caddy_binary.exists())
        self.assertFalse(self.paths.web_service_file.exists())
        self.installer.firewall.allow_tcp.assert_has_calls([call(22), call(443)])

    def test_initial_settings_change_automatically_provisions_web_for_old_binary(self):
        self.inventory.add_user("alice")
        self.inventory.add_secret("alice")
        self.systemd.write_units(self.paths.self_install_path)
        self.paths.binary_file.parent.mkdir(parents=True)
        self.paths.binary_file.write_bytes(b"old native telemt")
        self.controller.apply_form_settings(self.web)
        self.assertEqual(self.settings.load().proxy_mode, "both")
        self.assertTrue(self.paths.web_service_file.exists())
        self.source.install.assert_called_with("update", "", allow_build=False, require_web=True)

    def test_external_frontend_is_explicit_and_does_not_install_caddy(self):
        settings = replace(self.web, web_frontend="external")
        self.controller.setup_from_form(settings)
        self.assertFalse(self.paths.caddy_binary.exists())
        self.assertEqual(settings.public_ports, {443, 8443})

    def test_reserved_auto_https_ports_and_staging_settings(self):
        self.assertEqual(self.web.public_ports, {80, 443, 8443})
        for changes in ({"mt_port": 80}, {"web_port": 80}, {"stats_port": 80}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                replace(self.web, **changes).validate()
        self.settings.update(apply_runtime=False, **self.web.to_dict())
        self.settings.firewall.allow_tcp.assert_not_called()

    def test_port_conflict_restores_owned_service_and_does_not_install(self):
        self.systemd.write_units(self.paths.self_install_path)
        self.manager.reset_mock()
        with patch.object(self.https, "check_ports_available", side_effect=ServiceError("web_port_in_use:443")):
            with self.assertRaisesRegex(ServiceError, "web_port_in_use:443"):
                self.installer.initial_setup(self.web, self.paths.self_install_path, SetupOptions())
        self.source.install.assert_not_called()
        self.manager.start.assert_called_once_with("telemt.service")

    def test_unready_runtime_does_not_report_success(self):
        self.systemd.write_units(self.paths.self_install_path)
        with patch("services.install_service.socket.create_connection", side_effect=ConnectionRefusedError()):
            with self.assertRaisesRegex(ServiceError, "setup_runtime_failed"):
                WAIT_RUNTIME_READY(self.installer, self.web, timeout=0)

    def test_disabling_web_stops_managed_https_before_native_restart(self):
        self.controller.setup_from_form(self.web)
        self.manager.reset_mock()
        self.controller.update_settings(proxy_mode="mtproto", mt_port=443)
        calls = self.manager.mock_calls
        self.assertLess(calls.index(call.disable("mtp-manager-web.service")), calls.index(call.restart("telemt.service")))
        self.assertFalse(self.paths.web_state_file.exists())


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.paths = ProjectPaths(root=root, mt_dir=root / "telemt", conf_dir=root / "conf", data_dir=root / "data")
        self.https = HttpsService(Mock(), Mock(), JsonStorage(), self.paths)

    @staticmethod
    def archive():
        result = io.BytesIO()
        with tarfile.open(fileobj=result, mode="w:gz") as archive:
            member = tarfile.TarInfo("caddy")
            member.size = len(b"test binary")
            archive.addfile(member, io.BytesIO(b"test binary"))
        return result.getvalue()

    def test_caddy_download_is_verified_before_binary_write(self):
        data = self.archive()
        asset = f"caddy_{self.https.CADDY_VERSION}_linux_amd64.tar.gz"
        # Current Caddy release manifests use SHA512.
        checksum = f"{hashlib.sha512(data).hexdigest()}  {asset}\n".encode()
        with patch("services.https_service.os.uname", return_value=Mock(machine="x86_64")), \
             patch("services.https_service.urllib.request.urlopen", side_effect=[io.BytesIO(data), io.BytesIO(checksum)]):
            self.https.install_binary()
        self.assertEqual(self.paths.caddy_binary.read_bytes(), b"test binary")
        self.assertEqual(self.paths.caddy_binary.stat().st_mode & 0o777, 0o755)

    def test_corrupt_download_is_not_installed(self):
        with patch("services.https_service.os.uname", return_value=Mock(machine="x86_64")), \
             patch("services.https_service.urllib.request.urlopen", side_effect=[io.BytesIO(b"corrupt"), io.BytesIO(b"bad checksum")]):
            with self.assertRaisesRegex(ServiceError, "web_caddy_checksum_failed"):
                self.https.install_binary()
        self.assertFalse(self.paths.caddy_binary.exists())

    def test_caddy_config_validation_failure_preserves_previous_config(self):
        self.paths.caddy_config_file.parent.mkdir(parents=True)
        self.paths.caddy_config_file.write_text("previous config")
        self.https.shell.run.side_effect = ServiceError("invalid config")
        with self.assertRaises(ServiceError):
            self.https.configure(AppSettings(proxy_mode="web", web_domain="proxy.example.com", web_public_ip="8.8.8.8"))
        self.assertEqual(self.paths.caddy_config_file.read_text(), "previous config")
        self.assertFalse(self.paths.caddy_config_file.with_suffix(".candidate").exists())

    def test_current_system_rust_requires_no_download(self):
        shell = Mock()
        shell.run.return_value = CommandResult([], 0, "rustc 1.90.0", "")
        with patch("infra.rust.shutil.which", return_value="/usr/bin/tool"), patch("infra.rust.urllib.request.urlopen") as download:
            cargo, env = ensure_cargo(shell, self.paths.data_dir / "rust", "1.88")
        self.assertEqual((cargo, env), ("cargo", None))
        download.assert_not_called()

    def test_package_install_cannot_wait_for_hidden_debian_prompts(self):
        shell = Mock()
        packages = PackageManager(shell, DistroInfo("debian", "13", (), "debian"))
        packages.install(["ca-certificates"])
        install = shell.run.call_args_list[-1]
        self.assertEqual(install.kwargs["env"]["DEBIAN_FRONTEND"], "noninteractive")
        self.assertIn("Dpkg::Options::=--force-confold", install.args[0])

    def test_old_system_rust_installs_isolated_toolchain(self):
        shell = Mock()
        shell.run.side_effect = [CommandResult([], 0, "rustc 1.75.0", ""),
                                 CommandResult([], 0, "", ""), CommandResult([], 0, "rustc 1.90.0", "")]
        data = b"test rustup installer"
        with patch("infra.rust.shutil.which", return_value="/usr/bin/tool"), \
             patch("infra.rust.os.uname", return_value=Mock(machine="x86_64")), \
             patch("infra.rust.urllib.request.urlopen", side_effect=[io.BytesIO(data), io.BytesIO(hashlib.sha256(data).hexdigest().encode())]):
            cargo, env = ensure_cargo(shell, self.paths.data_dir / "rust", "1.88")
        self.assertTrue(cargo.startswith(str(self.paths.data_dir)))
        self.assertEqual(env["CARGO_HOME"], str(self.paths.data_dir / "rust/cargo"))
        self.assertIn("--no-modify-path", shell.run.call_args_list[1].args[0])
