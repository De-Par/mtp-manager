from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.containers import DynamicContainer, Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Box, Button, Dialog, Frame, Label, TextArea

from controller import AppController
from ui.backend import UIBackend
from ui.screens import (
    dashboard_screen,
    language_screen,
    maintenance_screen,
    reports_screen,
    service_screen,
    setup_screen,
    users_screen,
)
from ui.state import UIState
from ui.theme import APP_STYLE

SCREEN_ORDER = ["dashboard", "setup", "users", "service", "reports", "maintenance", "language"]
SCREEN_LABELS = {
    "dashboard": "Dashboard",
    "setup": "Setup & Updates",
    "users": "Users & Secrets",
    "service": "Service",
    "reports": "Status & Reports",
    "maintenance": "Maintenance",
    "language": "Language",
}


class PromptToolkitApp(UIBackend):
    def run(self, controller: AppController) -> int:
        state = UIState(
            current_screen="dashboard",
            status_message="Tab to move focus. Enter or mouse click to run actions. Left/Right switch screens.",
            selected_user=controller.selected_or_first_user(),
            selected_secret_id=None,
        )
        state.selected_secret_id = controller.selected_or_first_secret_id(state.selected_user, state.selected_secret_id)
        floats: list[Float] = []

        def invalidate() -> None:
            get_app().invalidate()

        def set_status(message: str) -> None:
            state.status_message = message
            invalidate()

        def close_dialog() -> None:
            floats.clear()
            invalidate()

        def show_message(title: str, text: str) -> None:
            dialog = Dialog(
                title=title,
                body=Box(TextArea(text=text, read_only=True, scrollbar=True), padding=1),
                buttons=[Button(text="OK", handler=close_dialog)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def show_error(exc: Exception) -> None:
            show_message("Error", str(exc))

        def run_action(fn) -> None:  # type: ignore[no-untyped-def]
            try:
                result = fn()
            except Exception as exc:
                show_error(exc)
                return
            state.selected_user = controller.selected_or_first_user(state.selected_user)
            state.selected_secret_id = controller.selected_or_first_secret_id(state.selected_user, state.selected_secret_id)
            if result is not None:
                set_status(str(result))
            else:
                invalidate()

        def switch_screen(name: str) -> None:
            state.current_screen = name
            state.selected_user = controller.selected_or_first_user(state.selected_user)
            state.selected_secret_id = controller.selected_or_first_secret_id(state.selected_user, state.selected_secret_id)
            set_status(f"Screen: {SCREEN_LABELS[name]}")

        def select_user(user_name: str) -> None:
            state.selected_user = user_name
            state.selected_secret_id = controller.selected_or_first_secret_id(user_name, state.selected_secret_id)
            set_status(f"Selected user: {user_name}")

        def select_secret(secret_id: int) -> None:
            state.selected_secret_id = secret_id
            set_status(f"Selected secret: {secret_id}")

        def cycle_user(direction: int) -> None:
            state.selected_user = (
                controller.next_user(state.selected_user)
                if direction > 0
                else controller.previous_user(state.selected_user)
            )
            state.selected_secret_id = controller.selected_or_first_secret_id(state.selected_user, state.selected_secret_id)
            invalidate()

        def cycle_secret(direction: int) -> None:
            state.selected_secret_id = (
                controller.next_secret_id(state.selected_user, state.selected_secret_id)
                if direction > 0
                else controller.previous_secret_id(state.selected_user, state.selected_secret_id)
            )
            invalidate()

        def open_add_user_dialog() -> None:
            name_field = TextArea(multiline=False)

            def accept() -> None:
                user_name = name_field.text.strip()
                close_dialog()
                run_action(lambda: controller.add_user(user_name))

            dialog = Dialog(
                title="Add User",
                body=HSplit([Label(text="User name"), name_field]),
                buttons=[Button(text="Save", handler=accept), Button(text="Cancel", handler=close_dialog)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def open_add_secret_dialog() -> None:
            selected = controller.selected_or_first_user(state.selected_user)
            if not selected:
                show_message("Users", "Create a user first.")
                return
            note_field = TextArea(multiline=False)

            def accept() -> None:
                note = note_field.text.strip()
                close_dialog()
                run_action(lambda: controller.add_secret(selected, note))

            dialog = Dialog(
                title=f"Add Secret: {selected}",
                body=HSplit([Label(text="Note"), note_field]),
                buttons=[Button(text="Save", handler=accept), Button(text="Cancel", handler=close_dialog)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def run_on_selected_secret(action) -> None:  # type: ignore[no-untyped-def]
            secret_id = controller.selected_or_first_secret_id(state.selected_user, state.selected_secret_id)
            if secret_id is None:
                show_message("Secrets", "Selected user has no secrets.")
                return
            state.selected_secret_id = secret_id
            run_action(lambda: action(secret_id))

        def open_settings_dialog() -> None:
            current = controller.load_settings()
            mt_port_field = TextArea(text=str(current.mt_port), multiline=False)
            stats_port_field = TextArea(text=str(current.stats_port), multiline=False)
            workers_field = TextArea(text=str(current.workers), multiline=False)
            fake_tls_field = TextArea(text=current.fake_tls_domain, multiline=False)
            ad_tag_field = TextArea(text=current.ad_tag, multiline=False)
            lang_field = TextArea(text=current.ui_lang, multiline=False)

            def accept() -> None:
                close_dialog()
                run_action(
                    lambda: controller.update_settings(
                        mt_port=int(mt_port_field.text.strip()),
                        stats_port=int(stats_port_field.text.strip()),
                        workers=int(workers_field.text.strip()),
                        fake_tls_domain=fake_tls_field.text.strip(),
                        ad_tag=ad_tag_field.text.strip(),
                        ui_lang=lang_field.text.strip(),
                    )
                )

            dialog = Dialog(
                title="Edit Settings",
                body=HSplit(
                    [
                        Label(text="Client port"),
                        mt_port_field,
                        Label(text="Stats port"),
                        stats_port_field,
                        Label(text="Workers"),
                        workers_field,
                        Label(text="Fake TLS domain"),
                        fake_tls_field,
                        Label(text="Ad tag"),
                        ad_tag_field,
                        Label(text="UI language (en/ru)"),
                        lang_field,
                    ]
                ),
                buttons=[Button(text="Save", handler=accept), Button(text="Cancel", handler=close_dialog)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def confirm_factory_reset() -> None:
            def accept() -> None:
                close_dialog()
                run_action(lambda: controller.factory_reset(remove_swap=False))

            dialog = Dialog(
                title="Danger Zone",
                body=Box(Label(text="Remove all MTProxy Manager managed artifacts?"), padding=1),
                buttons=[Button(text="Reset", handler=accept), Button(text="Cancel", handler=close_dialog)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def confirm_for_selected_user(title: str, body: str, action) -> None:  # type: ignore[no-untyped-def]
            selected = controller.selected_or_first_user(state.selected_user)
            if not selected:
                show_message("Users", "No user selected.")
                return

            def accept() -> None:
                close_dialog()
                run_action(lambda: action(selected))

            dialog = Dialog(
                title=title,
                body=Box(Label(text=body.format(user=selected)), padding=1),
                buttons=[Button(text="Confirm", handler=accept), Button(text="Cancel", handler=close_dialog)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def confirm_for_selected_secret(title: str, body: str, action) -> None:  # type: ignore[no-untyped-def]
            secret_id = controller.selected_or_first_secret_id(state.selected_user, state.selected_secret_id)
            if secret_id is None:
                show_message("Secrets", "No secret selected.")
                return

            def accept() -> None:
                close_dialog()
                run_action(lambda: action(secret_id))

            dialog = Dialog(
                title=title,
                body=Box(Label(text=body.format(secret_id=secret_id)), padding=1),
                buttons=[Button(text="Confirm", handler=accept), Button(text="Cancel", handler=close_dialog)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def screen_text() -> str:
            state.selected_user = controller.selected_or_first_user(state.selected_user)
            state.selected_secret_id = controller.selected_or_first_secret_id(state.selected_user, state.selected_secret_id)
            if state.current_screen == "dashboard":
                return dashboard_screen(controller)
            if state.current_screen == "setup":
                return setup_screen(controller)
            if state.current_screen == "users":
                return users_screen(controller, state.selected_user, state.selected_secret_id)
            if state.current_screen == "service":
                return service_screen(controller)
            if state.current_screen == "reports":
                report = reports_screen(controller)
                exports = controller.export_text_for_user(state.selected_user)
                return f"{report}\n\nSelected user export:\n{exports}"
            if state.current_screen == "maintenance":
                return maintenance_screen(controller)
            if state.current_screen == "language":
                return language_screen(controller)
            return "Unknown screen"

        def build_users_master_detail() -> Box:
            users = controller.list_users()
            if not users:
                return Box(Label(text="No users yet. Use 'Add User' to create the first entry."), padding=1)

            user_buttons = [
                Button(
                    text=f"{'>' if user.name == state.selected_user else ' '} {user.name} [{'on' if user.enabled else 'off'}]",
                    handler=lambda target=user.name: select_user(target),
                )
                for user in users
            ]
            selected_user = controller.get_user(state.selected_user)
            secret_buttons = []
            if selected_user:
                secret_buttons = [
                    Button(
                        text=f"{'*' if secret.id == state.selected_secret_id else ' '} #{secret.id} [{'on' if secret.enabled else 'off'}] {secret.note or '-'}",
                        handler=lambda secret_id=secret.id: select_secret(secret_id),
                    )
                    for secret in selected_user.secrets
                ]
            if not secret_buttons:
                secret_buttons = [Button(text="No secrets", handler=lambda: None)]

            details = controller.selected_detail_text(state.selected_user, state.selected_secret_id)
            return Box(
                VSplit(
                    [
                        Frame(Box(HSplit(user_buttons, padding=1), padding=1), title="Users", width=28),
                        Frame(Box(HSplit(secret_buttons, padding=1), padding=1), title="Secrets", width=34),
                        Frame(Box(Window(content=FormattedTextControl(text=details), wrap_lines=True), padding=1), title="Details"),
                    ]
                ),
                padding=0,
            )

        def build_content():
            if state.current_screen == "users":
                return build_users_master_detail()
            return Box(Window(content=FormattedTextControl(text=lambda: screen_text())), padding=1)

        def build_nav() -> Box:
            buttons = [Button(text=SCREEN_LABELS[name], handler=lambda target=name: switch_screen(target)) for name in SCREEN_ORDER]
            return Box(HSplit(buttons, padding=1), padding=1)

        def build_actions() -> Box:
            buttons: list[Button]
            if state.current_screen == "dashboard":
                buttons = [
                    Button(text="Refresh", handler=lambda: set_status("Dashboard refreshed")),
                    Button(text="Edit Settings", handler=open_settings_dialog),
                    Button(text="Next User", handler=lambda: cycle_user(1)),
                ]
            elif state.current_screen == "setup":
                buttons = [
                    Button(text="Initial Setup", handler=lambda: run_action(lambda: controller.run_setup(source_mode="fresh"))),
                    Button(text="Update Source", handler=lambda: run_action(controller.run_update)),
                    Button(text="Rebuild", handler=lambda: run_action(controller.run_rebuild)),
                    Button(text="Reinstall Units", handler=lambda: run_action(controller.run_reinstall_units)),
                    Button(text="Refresh Proxy Config", handler=lambda: run_action(controller.run_refresh_proxy_config)),
                    Button(text="Refresh Runtime", handler=lambda: run_action(controller.run_refresh_runtime)),
                    Button(text="Edit Settings", handler=open_settings_dialog),
                ]
            elif state.current_screen == "users":
                buttons = [
                    Button(text="Prev User", handler=lambda: cycle_user(-1)),
                    Button(text="Next User", handler=lambda: cycle_user(1)),
                    Button(text="Prev Secret", handler=lambda: cycle_secret(-1)),
                    Button(text="Next Secret", handler=lambda: cycle_secret(1)),
                    Button(text="Add User", handler=open_add_user_dialog),
                    Button(text="Add Secret", handler=open_add_secret_dialog),
                    Button(text="Enable User", handler=lambda: run_action(lambda: controller.set_user_enabled(controller.selected_or_first_user(state.selected_user) or "", True))),
                    Button(text="Disable User", handler=lambda: run_action(lambda: controller.set_user_enabled(controller.selected_or_first_user(state.selected_user) or "", False))),
                    Button(text="Rotate User", handler=lambda: run_action(lambda: controller.rotate_user(controller.selected_or_first_user(state.selected_user) or ""))),
                    Button(text="Delete User", handler=lambda: confirm_for_selected_user("Delete User", "Delete user {user} and all its secrets?", controller.delete_user)),
                    Button(text="Enable Secret", handler=lambda: run_on_selected_secret(lambda secret_id: controller.set_secret_enabled(secret_id, True))),
                    Button(text="Disable Secret", handler=lambda: run_on_selected_secret(lambda secret_id: controller.set_secret_enabled(secret_id, False))),
                    Button(text="Rotate Secret", handler=lambda: run_on_selected_secret(controller.rotate_secret)),
                    Button(text="Delete Secret", handler=lambda: confirm_for_selected_secret("Delete Secret", "Delete secret #{secret_id}?", controller.delete_secret)),
                ]
            elif state.current_screen == "service":
                buttons = [
                    Button(text="Start", handler=lambda: run_action(controller.service_start)),
                    Button(text="Stop", handler=lambda: run_action(controller.service_stop)),
                    Button(text="Restart", handler=lambda: run_action(controller.service_restart)),
                    Button(text="Status", handler=lambda: show_message("Service Status", controller.service_status_text())),
                    Button(text="Logs", handler=lambda: show_message("Service Logs", controller.service_logs_text())),
                    Button(text="Unit", handler=lambda: show_message("Unit Preview", controller.service_unit_preview())),
                ]
            elif state.current_screen == "reports":
                buttons = [
                    Button(text="Refresh Report", handler=lambda: set_status("Diagnostics refreshed")),
                    Button(text="Show Export", handler=lambda: show_message("Exports", controller.export_text_for_user(state.selected_user))),
                    Button(text="Export To File", handler=lambda: run_action(lambda: controller.export_selected_user_to_file(state.selected_user))),
                ]
            elif state.current_screen == "maintenance":
                buttons = [
                    Button(text="Cleanup Runtime", handler=lambda: run_action(controller.cleanup_runtime)),
                    Button(text="Cleanup Logs", handler=lambda: run_action(controller.cleanup_logs)),
                    Button(text="Factory Reset", handler=confirm_factory_reset),
                ]
            elif state.current_screen == "language":
                buttons = [
                    Button(text="English", handler=lambda: run_action(lambda: controller.set_language("en"))),
                    Button(text="Russian", handler=lambda: run_action(lambda: controller.set_language("ru"))),
                ]
            else:
                buttons = [Button(text="No actions", handler=lambda: None)]
            return Box(HSplit(buttons, padding=1), padding=1)

        status_control = FormattedTextControl(text=lambda: state.status_message)
        bindings = KeyBindings()

        @bindings.add("q")
        @bindings.add("c-c")
        def _quit(event) -> None:  # type: ignore[no-untyped-def]
            event.app.exit(result=0)

        @bindings.add("left")
        def _prev_screen(event) -> None:  # type: ignore[no-untyped-def]
            index = SCREEN_ORDER.index(state.current_screen)
            switch_screen(SCREEN_ORDER[(index - 1) % len(SCREEN_ORDER)])

        @bindings.add("right")
        def _next_screen(event) -> None:  # type: ignore[no-untyped-def]
            index = SCREEN_ORDER.index(state.current_screen)
            switch_screen(SCREEN_ORDER[(index + 1) % len(SCREEN_ORDER)])

        @bindings.add("n")
        def _next_user(event) -> None:  # type: ignore[no-untyped-def]
            cycle_user(1)

        @bindings.add("p")
        def _prev_user(event) -> None:  # type: ignore[no-untyped-def]
            cycle_user(-1)

        @bindings.add("j")
        def _next_secret(event) -> None:  # type: ignore[no-untyped-def]
            cycle_secret(1)

        @bindings.add("k")
        def _prev_secret(event) -> None:  # type: ignore[no-untyped-def]
            cycle_secret(-1)

        root = FloatContainer(
            content=HSplit(
                [
                    VSplit(
                        [
                            Frame(DynamicContainer(build_nav), title="Screens", width=24),
                            Frame(DynamicContainer(build_content), title="Content"),
                            Frame(DynamicContainer(build_actions), title="Actions", width=30),
                        ]
                    ),
                    Window(content=status_control, height=1, style="class:status"),
                ]
            ),
            floats=floats,
        )

        app = Application(
            layout=Layout(root),
            key_bindings=bindings,
            full_screen=True,
            mouse_support=True,
            style=APP_STYLE,
        )
        return int(app.run())
