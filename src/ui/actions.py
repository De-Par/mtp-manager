"""Action definitions and translation helpers for the Textual UI"""

from __future__ import annotations

from collections.abc import Callable

from ui.modals import ActionSpec

TranslatorFn = Callable[[str, str | None], str]

ACTION_LABEL_KEYS = {
    "back": "back",
    "more": "more",
    "configure_menu": "configure",
    "service_menu": "service_control",
    "source_menu": "source",
    "refresh": "refresh",
    "setup": "setup",
    "edit_settings": "edit_settings",
    "show_export": "show_export",
    "clear_activity": "clear_activity",
    "initial_setup": "initial_setup",
    "update_source": "update_source",
    "rebuild": "rebuild",
    "install_ref": "install_ref",
    "reinstall_units": "reinstall_units",
    "add_user": "add_user",
    "user_configure": "configure",
    "user_secrets": "secrets",
    "add_secret": "add_secret",
    "enable_user": "enable_user",
    "disable_user": "disable_user",
    "rotate_user": "rotate_user",
    "delete_user": "delete_user",
    "enable_secret": "enable_secret",
    "disable_secret": "disable_secret",
    "rotate_secret": "rotate_secret",
    "delete_secret": "delete_secret",
    "export_to_file": "export_to_file",
    "service_start": "start",
    "service_stop": "stop",
    "service_restart": "restart",
    "service_status": "status",
    "service_logs": "logs",
    "service_cleanup": "service_cleanup",
    "cleanup_logs": "cleanup_logs",
    "factory_reset": "factory_reset",
    "quit_app": "quit",
    "lang_en": "english",
    "lang_ru": "russian",
    "lang_zh": "chinese",
}

PRIMARY_ACTION_LIMIT = 6


def action_label(action: ActionSpec, translate: TranslatorFn) -> str:
    """Translate a single action label while preserving explicit fallbacks"""
    if action.label != action.key:
        return action.label
    key = ACTION_LABEL_KEYS.get(action.key)
    if key is None:
        return action.label
    return translate(key, action.label)


def translated_actions(
    actions: list[ActionSpec],
    translate: TranslatorFn,
) -> list[ActionSpec]:
    """Return translated copies of action specs for the current locale"""
    return [ActionSpec(action.key, action_label(action, translate), action.variant, action.classes) for action in actions]


def split_actions(actions: list[ActionSpec], primary_action_limit: int = PRIMARY_ACTION_LIMIT) -> tuple[list[ActionSpec], list[ActionSpec]]:
    """Split actions into the visible row and overflow bucket"""
    if len(actions) <= primary_action_limit:
        return actions, []
    primary = actions[: primary_action_limit - 1]
    secondary = actions[primary_action_limit - 1 :]
    primary.append(ActionSpec("more", "more"))
    return primary, secondary


def configure_actions() -> list[ActionSpec]:
    """Actions shown in the Configure modal"""
    return [
        ActionSpec("setup", "setup"),
        ActionSpec("edit_settings", "edit_settings"),
        ActionSpec("source_menu", "source_menu"),
        ActionSpec("service_cleanup", "service_cleanup", "warning"),
        ActionSpec("factory_reset", "factory_reset", "error"),
    ]


def source_actions() -> list[ActionSpec]:
    """Actions shown in the Telemt modal"""
    return [
        ActionSpec("install_ref", "install_ref"),
        ActionSpec("rebuild", "rebuild"),
        ActionSpec("update_source", "update_source"),
    ]


def service_actions(service_active: bool) -> list[ActionSpec]:
    """Actions shown in the Service modal"""
    return [
        ActionSpec("service_status", "service_status"),
        ActionSpec("service_logs", "service_logs"),
        ActionSpec("service_start", "service_start"),
        ActionSpec("service_restart", "service_restart"),
        ActionSpec("service_stop", "service_stop", "error"),
    ]


def primary_screen_actions(current_screen: str, has_history: bool) -> list[ActionSpec]:
    """Top-level action bar actions for the currently selected workspace"""
    actions: list[ActionSpec] = []
    if current_screen == "dashboard":
        actions.extend(
            [
                ActionSpec("refresh", "refresh"),
                ActionSpec("configure_menu", "configure_menu"),
                ActionSpec("service_menu", "service_menu"),
            ]
        )
        return actions
    if current_screen == "users":
        actions.extend(
            [
                ActionSpec("add_user", "add_user", "success"),
                ActionSpec("user_configure", "user_configure"),
                ActionSpec("delete_user", "delete_user", "error"),
            ]
        )
        return actions
    actions.append(ActionSpec("clear_activity", "clear_activity"))
    return actions
