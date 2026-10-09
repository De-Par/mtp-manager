from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import Mock

from textual.app import App
from textual.widgets import Input, Select

from controller import AppController
from i18n import Translator
from infra.storage import JsonStorage
from models.health import HealthCheck, HealthReport
from models.settings import AppSettings
from paths import ProjectPaths
from services.export_service import ExportService
from services.inventory_service import InventoryService
from services.proxy_runtime_service import ProxyRuntimeService
from services.settings_service import SettingsService
from ui.modals import SettingsScreen, UserSecretsScreen
from ui.textual_app import ManagerTextualApp


class WebUITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        paths = ProjectPaths(root=root, mt_dir=root / "telemt", conf_dir=root / "conf", data_dir=root / "data")
        storage = JsonStorage()
        inventory = InventoryService(storage, paths)
        inventory.add_user("alice")
        inventory.add_secret("alice")
        runtime = ProxyRuntimeService(storage, inventory, paths)
        paths.binary_file.parent.mkdir(parents=True)
        paths.binary_file.write_bytes(b"tg://webproxy?server=")
        systemd = Mock()
        systemd.is_installed.return_value = True
        systemd.state.return_value = "active"
        settings = SettingsService(storage, paths, runtime, systemd, Mock())
        settings.save(AppSettings())
        diagnostics = Mock()
        diagnostics.build_report.return_value = HealthReport([
            HealthCheck("public_ip", "public_ip", "8.8.8.8"),
            HealthCheck("telemt_version", "telemt_version", "3.5.14"),
            HealthCheck("service_status", "service_status", "active"),
        ])
        self.controller = AppController(
            Translator("ru"), settings, inventory, ExportService(), diagnostics, Mock(), Mock(), runtime, systemd, paths,
        )

    async def test_settings_dialog_switches_mode_and_saves_through_controller(self):
        app = ManagerTextualApp(self.controller)
        async with app.run_test(size=(80, 24)) as pilot:
            app._handle_ui_action("edit_settings")
            await pilot.pause()
            screen = app.screen
            self.assertIsInstance(screen, SettingsScreen)
            self.assertFalse(screen.query_one("#web-fields").display)
            # Use the keyboard to exercise the real Select interaction.
            await pilot.press("enter", "down", "enter")
            await pilot.pause()
            self.assertEqual(screen.query_one("#proxy_mode", Select).value, "web")
            self.assertTrue(screen.query_one("#web-fields").display)
            self.assertTrue(screen.query_one("#mt_port", Input).disabled)
            screen.query_one("#web_domain", Input).value = "proxy.example.com"
            screen.query_one("#web_public_ip", Input).value = "8.8.8.8"
            screen.query_one("#web_base_path", Input).value = "telegram/web"
            await pilot.click("#save")
            await app.workers.wait_for_complete()
            await pilot.pause()
            settings = self.controller.load_settings()
            self.assertEqual(settings.proxy_mode, "web")
            self.assertEqual(settings.web_base_path, "telegram/web")
            config = tomllib.loads(self.controller.paths.telemt_config_file.read_text())
            self.assertEqual(config["web"]["carrier"], "https")
            self.assertIn("tg://webproxy", self.controller.selected_secret_text("alice", 1))
            self.assertNotIn("tg://proxy", self.controller.selected_secret_text("alice", 1))

    async def test_combined_mode_displays_and_copies_all_five_link_rows(self):
        self.controller.update_settings(proxy_mode="both", mt_port=8443, web_domain="proxy.example.com", web_public_ip="8.8.8.8")
        app = ManagerTextualApp(self.controller)
        async with app.run_test(size=(120, 40)) as pilot:
            app.state.selected_user = "alice"
            app._open_user_secrets_screen(selected_secret_id=1)
            await pilot.pause()
            screen = app.screen
            self.assertIsInstance(screen, UserSecretsScreen)
            screen._list_active = True
            screen._update_detail()
            await pilot.pause()
            rows = list(screen.query(".user-secrets-link-row"))
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row.display for row in rows))
            self.assertTrue(screen._link_targets["user-secrets-link-copy-tg-3"].startswith("tg://webproxy"))
            self.assertTrue(screen._link_targets["user-secrets-link-copy-tg-4"].startswith("tg://webproxy"))
            self.assertFalse(screen.query_one("#user-secrets-link-copy-tme-3").display)
            self.assertNotIn("user-secrets-link-copy-tme-4", screen._link_targets)
            self.controller.update_settings(proxy_mode="web")
            screen._update_detail()
            await pilot.pause()
            self.assertEqual(sum(row.display for row in rows), 2)
            self.assertEqual(len(screen._link_targets), 2)
            self.assertTrue(all(link.startswith("tg://webproxy") for link in screen._link_targets.values()))
            screen._clear_links()
            self.assertFalse(any(row.display for row in rows))

    async def test_web_form_fits_narrow_terminal_and_can_switch_back(self):
        app = App()
        async with app.run_test(size=(48, 20)) as pilot:
            app.push_screen(SettingsScreen(AppSettings(proxy_mode="both", mt_port=8443)))
            await pilot.pause()
            screen = app.screen
            screen.query_one("#proxy_mode", Select).value = "mtproto"
            await pilot.pause()
            self.assertFalse(screen.query_one("#web-fields").display)
            self.assertFalse(screen.query_one("#mt_port", Input).disabled)
            self.assertLessEqual(screen.query_one("#confirm-dialog").region.width, 48)


if __name__ == "__main__":
    unittest.main()
