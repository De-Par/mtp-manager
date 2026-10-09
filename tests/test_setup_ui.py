from pathlib import Path
import socket
import unittest
from unittest.mock import Mock, patch

from rich.cells import cell_len
from textual.containers import VerticalScroll
from textual.widgets import Button, Collapsible, Input, Select, Static

from test_setup import SetupFixture
from ui.modals import FullscreenTextScreen, SetupScreen
from ui.textual_app import ManagerTextualApp


class SetupUITests(SetupFixture, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.make_fixture()
        self.mock_host()

    async def open_web_step(self, app, pilot):
        app._handle_ui_action("setup")
        await pilot.pause()
        await pilot.press("enter", "down", "enter")
        await pilot.click("#save")
        await pilot.pause()
        self.assertIsInstance(app.screen, SetupScreen)
        self.assertEqual(app.screen._setup_step, 2)

    async def test_first_run_entire_setup_from_menu_with_keyboard_input(self):
        app = ManagerTextualApp(self.controller)
        async with app.run_test(size=(80, 24)) as pilot:
            app._open_configure_menu()
            await pilot.pause()
            await pilot.click("#menu-setup")
            await pilot.pause()
            self.assertIsInstance(app.screen, SetupScreen)
            await pilot.press("enter", "down", "enter")
            await pilot.click("#save")
            await pilot.pause()
            self.assertEqual(app.focused.id, "web_domain")
            await pilot.press(*list("proxy.example.com"))
            await pilot.press("tab")
            self.assertEqual(app.focused.id, "web_public_ip")
            self.assertEqual(app.focused.value, "8.8.8.8")
            scroll = app.screen.query_one(".form-scroll", VerticalScroll)
            self.assertLessEqual(app.focused.region.bottom, scroll.region.bottom)
            await pilot.click("#save")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertEqual(self.settings.load().proxy_mode, "web")
            self.assertEqual(self.inventory.enabled_secret_count(), 1)
            self.assertTrue(self.paths.caddy_config_file.is_file())
            self.assertEqual(self.storage.load_json(self.paths.web_state_file, {})["status"], "ready")
            self.assertEqual(app.state.current_screen, "dashboard")
            self.assertIsInstance(app.screen, FullscreenTextScreen)
            self.assertIn("tg://webproxy", app.state.output_body)
            self.assertFalse(app._busy)
            app._copy_text = Mock()
            await pilot.click("#viewer-copy_setup_links")
            app._copy_text.assert_called_once()
            self.assertIn("tg://webproxy", app._copy_text.call_args.args[0])
            app.screen.action_close_viewer()
            await pilot.pause()
            await app.workers.wait_for_complete()
            self.assertEqual(app.state.output_body, "")

    async def test_invalid_form_keeps_user_input_and_does_not_install(self):
        app = ManagerTextualApp(self.controller)
        async with app.run_test(size=(80, 24)) as pilot:
            await self.open_web_step(app, pilot)
            screen = app.screen
            screen.query_one("#web_domain", Input).value = "not a domain"
            await pilot.click("#save")
            await pilot.pause()
            self.assertIs(app.screen, screen)
            self.assertTrue(screen.query_one("#form-error", Static).display)
            self.assertEqual(screen.query_one("#web_domain", Input).value, "not a domain")
            self.source.install.assert_not_called()

    async def test_dns_error_reopens_wizard_with_entered_values(self):
        app = ManagerTextualApp(self.controller)
        async with app.run_test(size=(80, 24)) as pilot:
            await self.open_web_step(app, pilot)
            app.screen.query_one("#web_domain", Input).value = "proxy.example.com"
            with patch("services.https_service.socket.getaddrinfo", side_effect=socket.gaierror("no DNS")):
                await pilot.click("#save")
                await app.workers.wait_for_complete()
                await pilot.pause()
            self.assertIsInstance(app.screen, SetupScreen)
            self.assertEqual(app.screen.query_one("#web_domain", Input).value, "proxy.example.com")
            self.assertEqual(app.screen.query_one("#proxy_mode", Select).value, "web")
            self.assertTrue(app.screen.query_one("#form-error", Static).display)
            self.assertEqual(self.inventory.enabled_secret_count(), 0)
            self.source.install.assert_not_called()

    async def test_back_preserves_values_and_combined_mode_chooses_safe_port(self):
        app = ManagerTextualApp(self.controller)
        async with app.run_test(size=(80, 24)) as pilot:
            app._handle_ui_action("setup")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#proxy_mode", Select).value = "both"
            await pilot.pause()
            self.assertEqual(screen.query_one("#mt_port", Input).value, "8443")
            await pilot.click("#save")
            await pilot.pause()
            screen.query_one("#web_domain", Input).value = "proxy.example.com"
            await pilot.click("#cancel")
            await pilot.pause()
            self.assertEqual(screen._setup_step, 1)
            await pilot.click("#save")
            await pilot.pause()
            self.assertEqual(screen.query_one("#web_domain", Input).value, "proxy.example.com")
            self.assertTrue(screen.query_one("#advanced-settings", Collapsible).collapsed)

    async def test_setup_controls_fit_sizes_and_locales(self):
        for locale in ("ru", "en", "zh"):
            for size in ((48, 20), (80, 24), (120, 40)):
                with self.subTest(locale=locale, size=size):
                    self.controller.translator.set_lang(locale)
                    app = ManagerTextualApp(self.controller)
                    async with app.run_test(size=size) as pilot:
                        await self.open_web_step(app, pilot)
                        for key in ("cancel", "save"):
                            button = app.screen.query_one(f"#{key}", Button)
                            self.assertGreaterEqual(button.content_region.width, cell_len(str(button.label)))
                            self.assertLessEqual(button.region.bottom, size[1])
                        self.assertLessEqual(app.screen.query_one("#confirm-dialog").region.width, size[0])
                        app.screen.query_one("#web_public_ip", Input).focus()
                        await pilot.pause()
                        scroll = app.screen.query_one(".form-scroll", VerticalScroll)
                        self.assertLessEqual(app.focused.region.bottom, scroll.region.bottom)


if __name__ == "__main__":
    unittest.main()
