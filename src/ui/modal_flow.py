"""Menu, modal, and dialog flow helpers for the main Textual app"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from errors import AppError
from ui.lists import secret_list_items
from ui.actions import configure_actions, server_actions, source_actions, translated_actions
from ui.modals import (
    ActionMenuScreen,
    ActionSpec,
    ConfirmScreen,
    FullscreenTextScreen,
    InstallRefScreen,
    ServerMenuScreen,
    SourceMenuScreen,
    TextInputScreen,
    UserConfigureMenuScreen,
    UserSecretsScreen,
)

CONFIGURE_MENU_HANDLED = "__configure_menu_handled__"
SOURCE_MENU_HANDLED = "__source_menu_handled__"


class ModalFlowMixin:
    """Keep modal builders and result handlers out of the main app controller"""

    @staticmethod
    def _format_secret_created_at(value: str) -> str:
        if not value:
            return "-"
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return parsed.strftime("%d.%m.%Y-%H:%M:%S")

    def _configure_actions(self) -> list[ActionSpec]:
        return configure_actions()

    def _source_actions(self) -> list[ActionSpec]:
        return source_actions()

    def _server_actions(self) -> list[ActionSpec]:
        return server_actions()

    def _run_cleanup(self) -> str:
        result = self.controller.service_cleanup()
        self._capture_hardware_snapshot()
        return result

    def _run_clear_server_logs(self) -> str:
        result = self.controller.clear_service_logs()
        self._capture_hardware_snapshot()
        return result

    def _server_logs_actions(self) -> list[ActionSpec]:
        return [
            ActionSpec("clear_server_logs", self._t("clean", "Clean"), "error", "viewer-danger-action"),
        ]

    def _server_status_actions(self) -> list[ActionSpec]:
        return [
            ActionSpec("copy_server_status", self._t("copy", "Copy")),
        ]

    def _handle_server_status_viewer_action(self, action: str) -> bool:
        if action != "copy_server_status":
            return False
        self._copy_text(self.controller.service_status_text())
        self.notify(self._t("copied_to_clipboard", "Copied to clipboard."), severity="information")
        return True

    def _open_server_logs_screen(self) -> None:
        self.push_screen(
            FullscreenTextScreen(
                self._t("server_logs_title"),
                self.controller.service_logs_text(),
                clear_before_close=True,
                actions=translated_actions(self._server_logs_actions(), self._t),
                close_label=self._t("close", "Close"),
            ),
            self._handle_server_logs_modal_result,
        )

    def _open_server_status_screen(self) -> None:
        self.push_screen(
            FullscreenTextScreen(
                self._t("server_status_title"),
                self.controller.service_status_text(),
                actions=translated_actions(self._server_status_actions(), self._t),
                action_handler=self._handle_server_status_viewer_action,
                close_label=self._t("close", "Close"),
            )
        )

    def _handle_server_logs_modal_result(self, result: str | None) -> None:
        if result == "clear_server_logs":
            self._reopen_screen_after_action = "server_logs"
            self._run_action(
                self._run_clear_server_logs,
                busy_label=f"{self._t('cleanup_logs', 'Cleanup logs')}...",
            )
            return

    def _handle_action_menu(self, action: str | None) -> None:
        if action is None:
            self.call_after_refresh(self._restore_default_focus)
            return
        if action:
            self._handle_ui_action(action)

    def _open_configure_menu(self) -> None:
        self.push_screen(
            ActionMenuScreen(
                self._t("configure"),
                translated_actions(self._configure_actions(), self._t),
                action_handler=self._handle_configure_menu_inline_action,
                close_label=self._t("close", "Close"),
            ),
            self._handle_configure_menu_result,
        )

    def _handle_configure_menu_inline_action(self, action: str) -> bool:
        if action != "cleanup":
            return False
        current_screen = self.screen
        self._reopen_screen_after_action = "configure_menu"
        self._run_action(
            self._run_cleanup,
            busy_label=f"{self._t('cleanup', 'Cleanup')}...",
        )
        if isinstance(current_screen, ActionMenuScreen):
            current_screen.dismiss(CONFIGURE_MENU_HANDLED)
        return True

    def _handle_configure_menu_result(self, action: str | None) -> None:
        if action == CONFIGURE_MENU_HANDLED:
            return
        self._handle_action_menu(action)

    def _build_server_menu_screen(self) -> ServerMenuScreen:
        return ServerMenuScreen(
            self._t("server"),
            translated_actions(self._server_actions(), self._t),
            open_status=self._open_server_status_screen,
            open_logs=self._open_server_logs_screen,
            action_handler=self._handle_server_menu_inline_action,
            close_label=self._t("close", "Close"),
        )

    def _open_server_menu(self) -> None:
        self.push_screen(self._build_server_menu_screen(), self._handle_server_menu_result)

    def _handle_server_menu_inline_action(self, action: str) -> bool:
        if action == "server_start":
            self._run_action(self.controller.service_start)
            return True
        if action == "server_restart":
            self._run_action(self.controller.service_restart)
            return True
        if action == "server_stop":
            self._run_action(self.controller.service_stop)
            return True
        return False

    def _handle_server_menu_result(self, action: str | None) -> None:
        if action is None:
            self.call_after_refresh(self._restore_default_focus)
            return
        self._handle_ui_action(action)

    def _refresh_open_server_menu(self) -> None:
        current_screen = self.screen
        if not isinstance(current_screen, ServerMenuScreen):
            return
        current_screen.update_actions(translated_actions(self._server_actions(), self._t))

    def _open_install_ref_screen(self) -> None:
        current_ref = self.controller.load_settings().telemt_ref
        self.push_screen(
            InstallRefScreen(
                self._t("install_ref_title", "Install telemt"),
                self._t("install_ref_prompt", "Tag or commit (blank = latest)"),
                value=current_ref,
                save_label=self._t("save", "Save"),
                cancel_label=self._t("cancel", "Cancel"),
            ),
            self._handle_install_ref,
        )

    def _open_source_menu(self) -> None:
        self.push_screen(
            SourceMenuScreen(
                self._t("manage_telemt", "Manage telemt"),
                translated_actions(self._source_actions(), self._t),
                action_handler=self._handle_source_menu_inline_action,
                close_label=self._t("close", "Close"),
            ),
            self._handle_source_menu_result,
        )

    def _handle_source_menu_inline_action(self, action: str) -> bool:
        current_screen = self.screen
        if action == "update_source":
            self._reopen_screen_after_action = "source_menu"
            self._run_action(
                self.controller.run_update,
                busy_label=f"{self._t('update_source', 'Sync')}...",
            )
            if isinstance(current_screen, SourceMenuScreen):
                current_screen.dismiss(SOURCE_MENU_HANDLED)
            return True
        if action == "rebuild":
            self._reopen_screen_after_action = "source_menu"
            self._run_action(
                self.controller.run_rebuild,
                busy_label=f"{self._t('rebuild', 'Reinstall')}...",
            )
            if isinstance(current_screen, SourceMenuScreen):
                current_screen.dismiss(SOURCE_MENU_HANDLED)
            return True
        if action == "install_ref":
            if isinstance(current_screen, SourceMenuScreen):
                current_screen.reset_interaction_state()
            self._open_install_ref_screen()
            return True
        return False

    def _handle_source_menu_result(self, action: str | None) -> None:
        if action is None:
            self._open_configure_menu()
            return
        if action == SOURCE_MENU_HANDLED:
            return
        if action == "update_source":
            self._reopen_screen_after_action = "source_menu"
            self._run_action(
                self.controller.run_update,
                busy_label=f"{self._t('update_source', 'Sync')}...",
            )
            return
        if action == "rebuild":
            self._reopen_screen_after_action = "source_menu"
            self._run_action(
                self.controller.run_rebuild,
                busy_label=f"{self._t('rebuild', 'Reinstall')}...",
            )
            return
        if action == "install_ref":
            self._open_install_ref_screen()
            return
        self._handle_action_menu(action)

    def _open_language_menu(self) -> None:
        actions = [
            ActionSpec("lang_en", self._t("english", "English")),
            ActionSpec("lang_ru", self._t("russian", "Russian")),
            ActionSpec("lang_zh", self._t("chinese", "Chinese")),
        ]
        self.push_screen(
            ActionMenuScreen(
                self._t("language"),
                actions,
                auto_focus_first=False,
                close_label=self._t("close", "Close"),
            ),
            self._handle_language_menu,
        )

    def _handle_language_menu(self, action: str | None) -> None:
        self.state.current_screen = "dashboard"
        if action:
            self._handle_ui_action(action)
            return
        self.call_after_refresh(self._restore_default_focus)
        self.run_worker(self.refresh_ui(), exclusive=True)

    def _change_language(self, lang: str) -> None:
        try:
            self.controller.set_language(lang)
        except Exception as exc:
            self._notify_result(self.controller.present_error(str(exc)), severity="error")
            self.run_worker(self.refresh_ui(), exclusive=True)
            return
        self.state.output_title = self._t("activity")
        self.state.output_body = ""
        self._notify_result(self._t("language_changed"))
        self.run_worker(self.refresh_ui(), exclusive=True)

    def _user_configure_actions(self) -> list[ActionSpec]:
        user = self._get_selected_user()
        actions: list[ActionSpec] = [
            ActionSpec("user_secrets", "user_secrets"),
            ActionSpec("rotate_user", "rotate_user", "warning"),
        ]
        if user is not None:
            if user.enabled:
                actions.append(ActionSpec("disable_user", "disable_user", "error"))
            else:
                actions.append(ActionSpec("enable_user", "enable_user", "success"))
        return actions

    def _open_user_configure_menu(self) -> None:
        user_name = self._selected_user_for_actions()
        if not user_name:
            self._notify_result(self._t("select_user_to_continue"), severity="warning")
            return
        self.push_screen(
            UserConfigureMenuScreen(
                f"👤 {self._t('manage', 'Manage')}: {user_name}",
                translated_actions(self._user_configure_actions(), self._t),
                close_label=self._t("close", "Close"),
                action_handler=self._handle_user_configure_inline_action,
            ),
            self._handle_user_configure_menu_result,
        )

    def _handle_user_configure_menu_result(self, action: str | None) -> None:
        if action is None:
            self.call_after_refresh(self._restore_default_focus)
            return
        self._handle_ui_action(action)

    def _handle_user_configure_inline_action(self, action: str) -> bool:
        user_name = self._selected_user_for_actions()
        if not user_name:
            self._notify_result(self._t("select_user_to_continue"), severity="warning")
            return True
        if action == "user_secrets":
            self._open_user_secrets_screen()
            return True
        if action == "enable_user":
            self._run_action(lambda: self.controller.set_user_enabled(user_name, True))
            return True
        if action == "disable_user":
            self._run_action(lambda: self.controller.set_user_enabled(user_name, False))
            return True
        if action == "rotate_user":
            self._run_action(lambda: self.controller.rotate_user(user_name))
            return True
        return False

    def _refresh_open_user_configure_menu(self) -> None:
        current_screen = self.screen
        if not isinstance(current_screen, UserConfigureMenuScreen):
            return
        current_screen.update_actions(translated_actions(self._user_configure_actions(), self._t))

    def _secret_detail_sections(self, secret_id: int | None) -> tuple[str, str, list[tuple[str, str | None, str | None]]]:
        user = self.controller.get_user(self.state.selected_user)
        secret = self.controller.get_secret(secret_id)
        if user is None or secret is None:
            return "", "", []
        settings = self.controller.load_settings()
        report = self.controller.diagnostics_service.build_report(settings)
        host = next((check.value for check in report.checks if check.key == "public_ip"), "") or "<public-ip>"
        bundle = self.controller.export_service.build_bundle(host, settings, user, secret)
        secret_label = secret.note or "-"
        overview = "\n".join(
            [
                f"{self._t('user_name')}: {user.name}",
                f"{self._t('secret_label', 'Secret')}: {secret_label}",
                f"{self._t('enabled_label', 'Enabled')}: {'🟢' if secret.enabled else '🔴'} {self._t('yes' if secret.enabled else 'no')}",
                f"{self._t('created_at')}: {self._format_secret_created_at(secret.created_at)}",
            ]
        )
        credentials = "\n".join(
            [
                f"{self._t('raw_secret')}: {secret.raw_secret}",
                f"DD: {bundle.links.padded_secret}",
                f"EE: {bundle.links.fake_tls_secret or self._t('none')}",
            ]
        )
        links = [
            (self._t("raw_secret"), bundle.links.tg_raw, bundle.links.tme_raw),
            ("DD", bundle.links.tg_padded, bundle.links.tme_padded),
            ("EE", bundle.links.tg_fake_tls, bundle.links.tme_fake_tls),
        ]
        return overview, credentials, links

    def _open_user_secrets_screen(self, *, selected_secret_id: int | None = None) -> None:
        user_name = self._selected_user_for_actions()
        user = self._get_selected_user()
        if not user_name or user is None:
            self._notify_result(self._t("select_user_to_continue"), severity="warning")
            return
        secret_items = secret_list_items(user)
        initial_secret_id = selected_secret_id if selected_secret_id is not None else self.state.selected_secret_id
        actions = [
            ActionSpec("add_secret", self._t("add", "Add"), "success"),
            ActionSpec("rotate_secret", self._t("rotate", "Rotate")),
            ActionSpec("delete_secret", self._t("delete", "Delete"), "error"),
        ]
        self.push_screen(
            UserSecretsScreen(
                f"🔐 {self._t('secrets')}",
                secret_items,
                selected_secret_id=initial_secret_id,
                detail_provider=self._secret_detail_sections,
                actions=actions,
                action_handler=self._handle_user_secrets_inline_action,
                secret_enabled_states={secret.id: secret.enabled for secret in user.secrets},
                list_title=self._t("secrets"),
                detail_title=self._t("overview"),
                credentials_title=self._t("credentials", "Credentials"),
                links_title=self._t("links"),
                enable_label=self._t("enable", "Enable"),
                disable_label=self._t("disable", "Disable"),
                close_label=self._t("close", "Close"),
                none_text=self._t("none", "none"),
                empty_list_message=self._t("user_secrets_empty"),
                empty_detail_message=self._t("secret_overview_unselected"),
                empty_detail_no_secrets_message=self._t("secret_overview_empty"),
                split_hint=self._t("split_resize_hint", "Drag to resize panels"),
                no_selection_message=self._t("select_secret_to_continue"),
            ),
            self._handle_user_secrets_screen_result,
        )

    def _handle_user_secrets_screen_result(self, result: tuple[str, int | None]) -> None:
        action, secret_id = result
        self.state.selected_secret_id = secret_id
        if action == "close":
            current_screen = self.screen
            if isinstance(current_screen, UserConfigureMenuScreen):
                current_screen.reset_interaction_state()
            else:
                self.call_after_refresh(self._restore_default_focus)
            return
        if action == "add_secret":
            self._reopen_screen_after_action = ("user_secrets", self.state.selected_user, None)
            self.push_screen(
                TextInputScreen(
                    self._t("add_secret"),
                    self._t("add_secret_prompt"),
                    save_label=self._t("save", "Save"),
                    cancel_label=self._t("cancel", "Cancel"),
                ),
                self._handle_add_secret,
            )
            return
        if action in {"enable_secret", "disable_secret", "rotate_secret", "delete_secret"}:
            self._reopen_screen_after_action = ("user_secrets", self.state.selected_user, secret_id)
            self._handle_ui_action(action)

    def _run_secret_action(self, action: Callable[[int], object]) -> None:
        if self.state.selected_secret_id is None:
            self._notify_result(self._t("select_secret_to_continue"), severity="warning")
            return
        self._run_action(lambda: action(self.state.selected_secret_id))

    def _handle_user_secrets_inline_action(self, action: str, secret_id: int | None) -> bool:
        if action == "add_secret":
            self.push_screen(
                TextInputScreen(
                    self._t("add_secret"),
                    self._t("add_secret_prompt"),
                    save_label=self._t("save", "Save"),
                    cancel_label=self._t("cancel", "Cancel"),
                ),
                self._handle_add_secret_from_user_secrets,
            )
            return True
        if secret_id is None:
            return False
        self.state.selected_secret_id = secret_id
        if action == "enable_secret":
            self._run_action(lambda: self.controller.set_secret_enabled(secret_id, True))
            return True
        if action == "disable_secret":
            self._run_action(lambda: self.controller.set_secret_enabled(secret_id, False))
            return True
        if action == "rotate_secret":
            self._run_action(lambda: self.controller.rotate_secret(secret_id))
            return True
        if action == "delete_secret":
            self.push_screen(
                ConfirmScreen(
                    self._t("delete_secret_title"),
                    self._delete_secret_confirm_text(secret_id),
                    self._t("delete", "Delete"),
                    cancel_label=self._t("cancel", "Cancel"),
                    confirm_variant="error",
                    center_message=True,
                ),
                self._handle_delete_secret_from_user_secrets,
            )
            return True
        return False

    def _handle_add_user(self, result: str | None) -> None:
        if result:
            self._run_action(
                lambda: self.controller.add_user(result),
                success_message=self._t("user_added").format(user=result),
            )
            return
        self.call_after_refresh(self._restore_default_focus)

    def _handle_add_secret(self, result: str | None) -> None:
        if result is not None and self.state.selected_user:
            self._run_action(
                lambda: self.controller.add_secret(self.state.selected_user or "", result),
                success_message=self._t("secret_added").format(user=self.state.selected_user),
            )
            return
        reopen_after_action = self._reopen_screen_after_action
        self._reopen_screen_after_action = None
        if isinstance(reopen_after_action, tuple) and len(reopen_after_action) == 3 and reopen_after_action[0] == "user_secrets":
            self._open_user_secrets_screen(selected_secret_id=self.state.selected_secret_id)
            return
        self.call_after_refresh(self._restore_default_focus)

    def _handle_add_secret_from_user_secrets(self, result: str | None) -> None:
        if result is None:
            return
        if not self.state.selected_user:
            self.call_after_refresh(self._restore_default_focus)
            return
        self._run_action(
            lambda: self.controller.add_secret(self.state.selected_user or "", result),
            success_message=self._t("secret_added").format(user=self.state.selected_user),
        )

    def _handle_delete_secret_from_user_secrets(self, confirmed: bool) -> None:
        if confirmed and self.state.selected_secret_id is not None:
            self._run_action(lambda: self.controller.delete_secret(self.state.selected_secret_id))

    def _handle_install_ref(self, result: str | None) -> None:
        current_screen = self.screen
        if isinstance(current_screen, SourceMenuScreen):
            current_screen.reset_interaction_state()
        if result is None:
            if not isinstance(current_screen, SourceMenuScreen):
                self._open_source_menu()
            return
        busy_label = self._t("installing_ref").format(ref=result.strip()) if result.strip() else self._t("installing_latest")
        self._reopen_screen_after_action = "source_menu"
        self._run_action(
            lambda: self.controller.install_telemt_ref(result),
            busy_label=busy_label,
        )
        if isinstance(current_screen, SourceMenuScreen):
            current_screen.dismiss(SOURCE_MENU_HANDLED)

    def _handle_settings_screen(self, result: dict[str, str] | None) -> None:
        if not result:
            self._open_configure_menu()
            return

        def apply_settings() -> str:
            try:
                mt_port = int(result["mt_port"])
            except ValueError as exc:
                raise AppError(self._t("invalid_integer_field").format(field=self._t("proxy_port"))) from exc
            try:
                stats_port = int(result["stats_port"])
            except ValueError as exc:
                raise AppError(self._t("invalid_integer_field").format(field=self._t("api_port"))) from exc
            try:
                workers = int(result["workers"])
            except ValueError as exc:
                raise AppError(self._t("invalid_integer_field").format(field=self._t("workers"))) from exc
            self.controller.update_settings(
                mt_port=mt_port,
                stats_port=stats_port,
                workers=workers,
                fake_tls_domain=result["fake_tls_domain"],
                ad_tag=result["ad_tag"],
            )
            return self._t("settings_saved_applied", "Settings saved and applied.")

        self._run_action(
            apply_settings,
            busy_label=f"{self._t('edit_settings', 'Edit')}...",
        )

    def _handle_delete_user(self, confirmed: bool) -> None:
        if confirmed and self.state.selected_user:
            self._run_action(lambda: self.controller.delete_user(self.state.selected_user or ""))
            return
        self.call_after_refresh(self._restore_default_focus)

    def _handle_delete_secret(self, confirmed: bool) -> None:
        if confirmed and self.state.selected_secret_id is not None:
            self._run_action(lambda: self.controller.delete_secret(self.state.selected_secret_id))
            return
        self.call_after_refresh(self._restore_default_focus)

    def _handle_factory_reset(self, confirmed: bool) -> None:
        if confirmed:
            self._run_action(
                lambda: self.controller.factory_reset(remove_swap=False),
                busy_label=f"{self._t('factory_reset', 'Factory Reset')}...",
            )
            return
        self._open_configure_menu()

    def _open_quit_confirmation(self) -> None:
        current_screen = self.screen
        if isinstance(current_screen, ConfirmScreen) and current_screen.title_text == self._t("quit_confirm_title", "Quit"):
            return
        self.push_screen(
            ConfirmScreen(
                self._t("quit_confirm_title", "Quit"),
                self._t("quit_confirm_message", "Close mtp-manager?"),
                self._t("quit_confirm_button", "Quit"),
                cancel_label=self._t("cancel", "Cancel"),
                confirm_variant="warning",
                center_message=True,
            ),
            self._handle_quit_confirmation,
        )

    def _handle_quit_confirmation(self, confirmed: bool) -> None:
        if confirmed:
            self.exit()
            return
        self.call_after_refresh(self._restore_default_focus)
