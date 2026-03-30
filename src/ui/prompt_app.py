from __future__ import annotations

from collections.abc import Callable
import shutil

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app, get_app_or_none
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit
from prompt_toolkit.layout.containers import DynamicContainer, Float, FloatContainer
from prompt_toolkit.layout.scrollable_pane import ScrollablePane
from prompt_toolkit.widgets import Box, Button, Dialog, Frame, Label, TextArea

from controller import AppController
from models.secret import SecretRecord, UserRecord
from models.settings import AppSettings
from ui.backend import UIBackend
from ui.panels import render_dashboard_panel, render_report_panel, render_settings_panel
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

DEFAULT_ACTIVITY_TITLE = "Activity"
DEFAULT_ACTIVITY_BODY = "Logs, exports, service status, and previews are shown here."


class PromptToolkitApp(UIBackend):
    def run(self, controller: AppController) -> int:
        state = UIState(
            current_screen="dashboard",
            status_message="Compact TUI loaded. Mouse clicks, wheel scroll, and keyboard shortcuts are enabled.",
            selected_user=None,
            selected_secret_id=None,
            output_title=DEFAULT_ACTIVITY_TITLE,
            output_body=DEFAULT_ACTIVITY_BODY,
        )
        floats: list[Float] = []
        users_snapshot: list[UserRecord] = []
        overview_body = ""
        inspector_body = ""

        def get_columns() -> int:
            app = get_app_or_none()
            if app is not None:
                return app.output.get_size().columns
            return shutil.get_terminal_size((120, 40)).columns

        def invalidate() -> None:
            get_app().invalidate()

        def set_status(message: str) -> None:
            state.status_message = message
            invalidate()

        def refresh_selection() -> None:
            nonlocal users_snapshot
            users_snapshot = controller.list_users()
            names = [user.name for user in users_snapshot]
            if not names:
                state.selected_user = None
                state.selected_secret_id = None
                return
            if state.selected_user not in names:
                state.selected_user = names[0]
            user = get_selected_user()
            if user is None or not user.secrets:
                state.selected_secret_id = None
                return
            secret_ids = [secret.id for secret in user.secrets]
            if state.selected_secret_id not in secret_ids:
                state.selected_secret_id = secret_ids[0]

        def get_selected_user() -> UserRecord | None:
            for user in users_snapshot:
                if user.name == state.selected_user:
                    return user
            return None

        def get_selected_secret(user: UserRecord | None = None) -> SecretRecord | None:
            owner = user or get_selected_user()
            if owner is None:
                return None
            for secret in owner.secrets:
                if secret.id == state.selected_secret_id:
                    return secret
            return None

        def set_activity(title: str, body: str) -> None:
            state.output_title = title
            state.output_body = body or "No output."
            invalidate()

        def clear_activity() -> None:
            set_activity(DEFAULT_ACTIVITY_TITLE, DEFAULT_ACTIVITY_BODY)

        def close_dialog() -> None:
            floats.clear()
            invalidate()

        def side_button_width() -> int:
            columns = get_columns()
            if columns >= 120:
                return 28
            if columns >= 90:
                return 24
            return max(16, columns - 10)

        def nav_button_width() -> int:
            columns = get_columns()
            if columns >= 120:
                return 18
            if columns >= 90:
                return 16
            if columns >= 70:
                return 14
            return 12

        def make_button(text: str, handler: Callable[[], None], *, width: int | None = None) -> Button:
            return Button(
                text=text,
                handler=handler,
                width=width or side_button_width(),
                left_symbol=" ",
                right_symbol=" ",
            )

        def make_text_area(text: str) -> TextArea:
            return TextArea(
                text=text,
                read_only=True,
                focusable=True,
                focus_on_click=True,
                scrollbar=True,
                wrap_lines=True,
            )

        def summarize_result(result: object) -> str:
            if isinstance(result, str):
                return result
            if isinstance(result, AppSettings):
                return "Settings updated"
            if isinstance(result, UserRecord):
                return f"User saved: {result.name}"
            if isinstance(result, SecretRecord):
                return f"Secret saved: #{result.id}"
            return "Action completed"

        def format_result(result: object) -> str:
            if isinstance(result, str):
                return result
            if isinstance(result, AppSettings):
                return render_settings_panel(result)
            if isinstance(result, UserRecord):
                return controller.selected_detail_text(result.name, None)
            if isinstance(result, SecretRecord):
                return controller.selected_detail_text(state.selected_user, result.id)
            return str(result)

        def show_message(title: str, text: str) -> None:
            dialog = Dialog(
                title=title,
                body=Box(
                    TextArea(
                        text=text,
                        read_only=True,
                        focusable=True,
                        focus_on_click=True,
                        scrollbar=True,
                        wrap_lines=True,
                    ),
                    padding=1,
                ),
                buttons=[make_button("OK", close_dialog, width=12)],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def show_error(exc: Exception) -> None:
            show_message("Error", str(exc))

        def open_confirm_dialog(
            title: str,
            body: str,
            on_confirm: Callable[[], None],
            *,
            confirm_text: str = "Confirm",
        ) -> None:
            def accept() -> None:
                close_dialog()
                on_confirm()

            dialog = Dialog(
                title=title,
                body=Box(Label(text=body), padding=1),
                buttons=[
                    make_button(confirm_text, accept, width=14),
                    make_button("Cancel", close_dialog, width=14),
                ],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def refresh_views() -> None:
            nonlocal overview_body, inspector_body
            refresh_selection()
            settings = controller.load_settings()
            selected_user = get_selected_user()
            selected_secret = get_selected_secret(selected_user)

            if state.current_screen == "dashboard":
                dashboard = controller.dashboard()
                overview_body = render_dashboard_panel(dashboard)
            elif state.current_screen == "setup":
                overview_body = (
                    render_settings_panel(settings)
                    + "\n\nRun setup, rebuild, unit reinstall, or runtime refresh from the context panel."
                )
            elif state.current_screen == "users":
                if selected_user is None:
                    overview_body = "No users yet.\n\nCreate the first user from the context panel."
                else:
                    overview_body = controller.selected_detail_text(state.selected_user, state.selected_secret_id)
            elif state.current_screen == "service":
                dashboard = controller.dashboard()
                overview_body = "\n".join(
                    [
                        f"State: {dashboard.service_status}",
                        f"Public IP: {dashboard.public_ip}",
                        f"Client port: {dashboard.mt_port}",
                        f"Stats port: {dashboard.stats_port}",
                        "",
                        "Use the context panel to start, stop, restart, or load service details.",
                    ]
                )
            elif state.current_screen == "reports":
                overview_body = render_report_panel(controller.diagnostics())
            elif state.current_screen == "maintenance":
                overview_body = "\n".join(
                    [
                        "Maintenance actions available:",
                        "- Cleanup runtime artifacts",
                        "- Cleanup logs and package cache",
                        "- Factory reset managed mtp-manager state",
                    ]
                )
            elif state.current_screen == "language":
                overview_body = f"Current language: {settings.ui_lang}\n\nSwitch the stored interface language from the context panel."
            else:
                overview_body = "Unknown screen"

            inspector_lines = [
                f"Screen: {SCREEN_LABELS[state.current_screen]}",
                f"Selected user: {selected_user.name if selected_user else '-'}",
                f"Selected secret: #{selected_secret.id}" if selected_secret else "Selected secret: -",
            ]
            if selected_user is not None:
                inspector_lines.extend(
                    [
                        "",
                        f"User enabled: {'on' if selected_user.enabled else 'off'}",
                        f"Secrets total: {len(selected_user.secrets)}",
                    ]
                )
            if selected_secret is not None:
                inspector_lines.extend(
                    [
                        f"Secret enabled: {'on' if selected_secret.enabled else 'off'}",
                        f"Created: {selected_secret.created_at or '-'}",
                        f"Note: {selected_secret.note or '-'}",
                    ]
                )
            inspector_body = "\n".join(inspector_lines)

        def run_action(
            fn: Callable[[], object],
            *,
            success_message: str | None = None,
            output_title: str | None = None,
        ) -> None:
            try:
                result = fn()
            except Exception as exc:
                show_error(exc)
                return
            refresh_views()
            state.status_message = success_message or summarize_result(result)
            if output_title is not None:
                state.output_title = output_title
                state.output_body = format_result(result)
            invalidate()

        def switch_screen(name: str) -> None:
            state.current_screen = name
            refresh_views()
            set_status(f"Opened {SCREEN_LABELS[name]}")

        def select_user(user_name: str) -> None:
            state.selected_user = user_name
            refresh_views()
            set_status(f"Selected user: {user_name}")

        def select_secret(secret_id: int) -> None:
            state.selected_secret_id = secret_id
            refresh_views()
            set_status(f"Selected secret: {secret_id}")

        def cycle_user(direction: int) -> None:
            refresh_selection()
            if not users_snapshot:
                return
            names = [user.name for user in users_snapshot]
            index = names.index(state.selected_user) if state.selected_user in names else 0
            state.selected_user = names[(index + direction) % len(names)]
            refresh_views()
            set_status(f"Selected user: {state.selected_user}")

        def cycle_secret(direction: int) -> None:
            refresh_selection()
            selected_user = get_selected_user()
            if selected_user is None or not selected_user.secrets:
                return
            secret_ids = [secret.id for secret in selected_user.secrets]
            index = secret_ids.index(state.selected_secret_id) if state.selected_secret_id in secret_ids else 0
            state.selected_secret_id = secret_ids[(index + direction) % len(secret_ids)]
            refresh_views()
            set_status(f"Selected secret: {state.selected_secret_id}")

        def open_add_user_dialog() -> None:
            name_field = TextArea(multiline=False)

            def accept() -> None:
                user_name = name_field.text.strip()
                close_dialog()
                run_action(
                    lambda: controller.add_user(user_name),
                    success_message=f"Added user: {user_name}",
                    output_title="User Created",
                )

            dialog = Dialog(
                title="Add User",
                body=HSplit([Label(text="User name"), name_field]),
                buttons=[
                    make_button("Save", accept, width=14),
                    make_button("Cancel", close_dialog, width=14),
                ],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def open_add_secret_dialog() -> None:
            refresh_selection()
            selected_user = get_selected_user()
            if selected_user is None:
                show_message("Users", "Create a user first.")
                return
            note_field = TextArea(multiline=False)

            def accept() -> None:
                note = note_field.text.strip()
                close_dialog()
                run_action(
                    lambda: controller.add_secret(selected_user.name, note),
                    success_message=f"Added secret for {selected_user.name}",
                    output_title="Secret Created",
                )

            dialog = Dialog(
                title=f"Add Secret: {selected_user.name}",
                body=HSplit([Label(text="Note"), note_field]),
                buttons=[
                    make_button("Save", accept, width=14),
                    make_button("Cancel", close_dialog, width=14),
                ],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

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
                    ),
                    success_message="Settings updated",
                    output_title="Settings",
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
                buttons=[
                    make_button("Save", accept, width=14),
                    make_button("Cancel", close_dialog, width=14),
                ],
                modal=True,
            )
            floats[:] = [Float(content=dialog)]
            invalidate()

        def confirm_factory_reset() -> None:
            open_confirm_dialog(
                "Danger Zone",
                "Remove all mtp-manager managed artifacts?",
                lambda: run_action(
                    lambda: controller.factory_reset(remove_swap=False),
                    output_title="Factory Reset",
                ),
                confirm_text="Reset",
            )

        def run_on_selected_secret(action: Callable[[int], object]) -> None:
            refresh_selection()
            selected_secret = get_selected_secret()
            if selected_secret is None:
                show_message("Secrets", "Selected user has no secrets.")
                return
            state.selected_secret_id = selected_secret.id
            run_action(lambda: action(selected_secret.id))

        def confirm_for_selected_user(title: str, body: str, action: Callable[[str], object]) -> None:
            refresh_selection()
            selected_user = get_selected_user()
            if selected_user is None:
                show_message("Users", "No user selected.")
                return
            open_confirm_dialog(
                title,
                body.format(user=selected_user.name),
                lambda: run_action(lambda: action(selected_user.name), output_title=title),
            )

        def confirm_for_selected_secret(title: str, body: str, action: Callable[[int], object]) -> None:
            refresh_selection()
            selected_secret = get_selected_secret()
            if selected_secret is None:
                show_message("Secrets", "No secret selected.")
                return
            open_confirm_dialog(
                title,
                body.format(secret_id=selected_secret.id),
                lambda: run_action(lambda: action(selected_secret.id), output_title=title),
            )

        def show_service_status() -> None:
            try:
                set_activity("Service Status", controller.service_status_text())
            except Exception as exc:
                show_error(exc)
                return
            set_status("Loaded service status")

        def show_service_logs() -> None:
            try:
                set_activity("Service Logs", controller.service_logs_text())
            except Exception as exc:
                show_error(exc)
                return
            set_status("Loaded service logs")

        def show_service_unit() -> None:
            try:
                set_activity("Unit Preview", controller.service_unit_preview())
            except Exception as exc:
                show_error(exc)
                return
            set_status("Loaded systemd unit preview")

        def show_selected_exports() -> None:
            try:
                set_activity(f"Exports: {state.selected_user or 'none'}", controller.export_text_for_user(state.selected_user))
            except Exception as exc:
                show_error(exc)
                return
            set_status("Loaded export bundle")

        def action_items() -> list[tuple[str, Callable[[], None]]]:
            if state.current_screen == "dashboard":
                return [
                    ("Refresh", lambda: (refresh_views(), set_status("Dashboard refreshed"))),
                    ("Edit Settings", open_settings_dialog),
                    ("Show Export", show_selected_exports),
                    ("Clear Activity", clear_activity),
                ]
            if state.current_screen == "setup":
                return [
                    ("Initial Setup", lambda: run_action(lambda: controller.run_setup(source_mode="fresh"))),
                    ("Update Source", lambda: run_action(controller.run_update)),
                    ("Rebuild", lambda: run_action(controller.run_rebuild)),
                    ("Reinstall Units", lambda: run_action(controller.run_reinstall_units)),
                    ("Refresh Config", lambda: run_action(controller.run_refresh_proxy_config)),
                    ("Refresh Runtime", lambda: run_action(controller.run_refresh_runtime)),
                    ("Edit Settings", open_settings_dialog),
                ]
            if state.current_screen == "users":
                return [
                    ("Prev User", lambda: cycle_user(-1)),
                    ("Next User", lambda: cycle_user(1)),
                    ("Prev Secret", lambda: cycle_secret(-1)),
                    ("Next Secret", lambda: cycle_secret(1)),
                    ("Add User", open_add_user_dialog),
                    ("Add Secret", open_add_secret_dialog),
                    ("Enable User", lambda: run_action(lambda: controller.set_user_enabled(state.selected_user or "", True))),
                    ("Disable User", lambda: run_action(lambda: controller.set_user_enabled(state.selected_user or "", False))),
                    ("Rotate User", lambda: run_action(lambda: controller.rotate_user(state.selected_user or ""))),
                    ("Delete User", lambda: confirm_for_selected_user("Delete User", "Delete user {user} and all its secrets?", controller.delete_user)),
                    ("Enable Secret", lambda: run_on_selected_secret(lambda secret_id: controller.set_secret_enabled(secret_id, True))),
                    ("Disable Secret", lambda: run_on_selected_secret(lambda secret_id: controller.set_secret_enabled(secret_id, False))),
                    ("Rotate Secret", lambda: run_on_selected_secret(controller.rotate_secret)),
                    ("Delete Secret", lambda: confirm_for_selected_secret("Delete Secret", "Delete secret #{secret_id}?", controller.delete_secret)),
                    ("Show Export", show_selected_exports),
                    ("Export To File", lambda: run_action(lambda: controller.export_selected_user_to_file(state.selected_user), output_title="Export File")),
                ]
            if state.current_screen == "service":
                return [
                    ("Start", lambda: run_action(controller.service_start)),
                    ("Stop", lambda: run_action(controller.service_stop)),
                    ("Restart", lambda: run_action(controller.service_restart)),
                    ("Status", show_service_status),
                    ("Logs", show_service_logs),
                    ("Unit Preview", show_service_unit),
                    ("Clear Activity", clear_activity),
                ]
            if state.current_screen == "reports":
                return [
                    ("Refresh", lambda: (refresh_views(), set_status("Diagnostics refreshed"))),
                    ("Show Export", show_selected_exports),
                    ("Export To File", lambda: run_action(lambda: controller.export_selected_user_to_file(state.selected_user), output_title="Export File")),
                    ("Service Logs", show_service_logs),
                    ("Clear Activity", clear_activity),
                ]
            if state.current_screen == "maintenance":
                return [
                    ("Cleanup Runtime", lambda: run_action(controller.cleanup_runtime)),
                    ("Cleanup Logs", lambda: run_action(controller.cleanup_logs)),
                    ("Factory Reset", confirm_factory_reset),
                    ("Clear Activity", clear_activity),
                ]
            if state.current_screen == "language":
                return [
                    ("English", lambda: run_action(lambda: controller.set_language("en"), success_message="Language changed to English", output_title="Settings")),
                    ("Russian", lambda: run_action(lambda: controller.set_language("ru"), success_message="Language changed to Russian", output_title="Settings")),
                    ("Clear Activity", clear_activity),
                ]
            return [("Clear Activity", clear_activity)]

        def nav_rows() -> list[list[str]]:
            columns = get_columns()
            row_size = 4 if columns >= 120 else 3 if columns >= 80 else 2
            return [SCREEN_ORDER[index : index + row_size] for index in range(0, len(SCREEN_ORDER), row_size)]

        def build_nav_panel() -> Box:
            rows = []
            for row in nav_rows():
                rows.append(
                    VSplit(
                        [
                            make_button(
                                f"{'●' if name == state.current_screen else '○'} {SCREEN_LABELS[name]}",
                                lambda target=name: switch_screen(target),
                                width=nav_button_width(),
                            )
                            for name in row
                        ],
                        padding=1,
                    )
                )
            return Box(HSplit(rows, padding=1), padding=0)

        def build_nav_frame():
            return Frame(
                DynamicContainer(build_nav_panel),
                title="Menu",
                height=len(nav_rows()) * 2 + 1,
            )

        def build_main_panel() -> Box:
            text = "\n\n".join(
                [
                    overview_body,
                    f"[{state.output_title}]",
                    state.output_body,
                ]
            )
            return Box(make_text_area(text), padding=1)

        def build_button_group(title: str, items: list[tuple[str, Callable[[], None]]]) -> HSplit:
            widgets: list[object] = [Label(text=title, style="class:section.title")]
            if not items:
                widgets.append(Label(text="Nothing here.", style="class:muted"))
            else:
                widgets.extend(make_button(label, handler) for label, handler in items)
            return HSplit(widgets, padding=1)

        def build_sidebar_panel() -> Box:
            widgets: list[object] = []
            selected_user = get_selected_user()

            if state.current_screen == "users":
                widgets.append(Label(text="Users", style="class:section.title"))
                if users_snapshot:
                    widgets.extend(
                        make_button(
                            f"{'●' if user.name == state.selected_user else '○'} {user.name} [{'on' if user.enabled else 'off'}]",
                            lambda target=user.name: select_user(target),
                        )
                        for user in users_snapshot
                    )
                else:
                    widgets.append(Label(text="No users yet.", style="class:muted"))

                widgets.append(Label(text="Secrets", style="class:section.title"))
                if selected_user and selected_user.secrets:
                    widgets.extend(
                        make_button(
                            f"{'●' if secret.id == state.selected_secret_id else '○'} #{secret.id} {secret.note or '-'}",
                            lambda target=secret.id: select_secret(target),
                        )
                        for secret in selected_user.secrets
                    )
                else:
                    widgets.append(Label(text="No secrets for selected user.", style="class:muted"))

            widgets.append(Label(text="Actions", style="class:section.title"))
            widgets.extend(make_button(label, handler) for label, handler in action_items())
            widgets.append(Label(text="Inspector", style="class:section.title"))
            widgets.append(Label(text=inspector_body or "No details.", style="class:muted"))

            body = ScrollablePane(
                HSplit(widgets, padding=1),
                show_scrollbar=True,
                display_arrows=False,
            )
            return Box(body, padding=1)

        def build_body():
            columns = get_columns()
            main_frame = Frame(DynamicContainer(build_main_panel), title=SCREEN_LABELS[state.current_screen])
            if columns >= 120:
                side_frame = Frame(DynamicContainer(build_sidebar_panel), title="Context", width=38)
                return VSplit([main_frame, side_frame], padding=1)
            side_height = 10 if columns >= 90 else 8
            side_frame = Frame(DynamicContainer(build_sidebar_panel), title="Context", height=side_height)
            return HSplit([main_frame, side_frame], padding=1)

        refresh_views()

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

        @bindings.add("r")
        def _refresh(event) -> None:  # type: ignore[no-untyped-def]
            refresh_views()
            set_status(f"Refreshed {SCREEN_LABELS[state.current_screen]}")

        root = FloatContainer(
            content=HSplit(
                [
                    Label(
                        text=lambda: (
                            f" mtp-manager | {SCREEN_LABELS[state.current_screen]} | "
                            f"user: {state.selected_user or '-'} | "
                            f"secret: {f'#{state.selected_secret_id}' if state.selected_secret_id is not None else '-'} "
                        ),
                        style="class:header",
                    ),
                    DynamicContainer(build_nav_frame),
                    DynamicContainer(build_body),
                    Label(
                        text=lambda: (
                            f" {state.status_message} | Left/Right sections | n/p users | j/k secrets | q quit "
                        ),
                        style="class:status",
                    ),
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
