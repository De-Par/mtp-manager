"""Selection and list-building helpers for sections, users, and secrets"""

from __future__ import annotations

from collections.abc import Callable

from models.secret import SecretRecord, UserRecord

LabelTranslateFn = Callable[[str, str | None], str]

SCREEN_ORDER = ["dashboard", "users", "language"]

SCREEN_LABEL_KEYS = {
    "dashboard": "dashboard",
    "users": "users_secrets",
    "language": "language",
}

SCREEN_EMOJIS = {
    "dashboard": "📊",
    "users": "👥",
    "language": "🌍",
}


def normalize_screen(screen: str) -> str:
    """Map legacy screen aliases back to the current top-level workspace ids"""
    return "dashboard" if screen in {"setup", "service", "maintenance", "reports"} else screen


def screen_label(screen: str, translate: LabelTranslateFn) -> str:
    """Translate a workspace label for the sections list"""
    return translate(SCREEN_LABEL_KEYS.get(screen, screen), screen)


def screen_menu_label(screen: str, translate: LabelTranslateFn) -> str:
    """Build the visible sections-list label including its emoji"""
    return f"{SCREEN_EMOJIS.get(screen, '•')} {screen_label(screen, translate)}"


def refresh_selection(
    users_snapshot: list[UserRecord],
    selected_user: str | None,
    selected_secret_id: int | None,
) -> tuple[str | None, int | None]:
    """Keep the selected user and secret pinned to valid current records"""
    names = [user.name for user in users_snapshot]
    if not names:
        return None, None
    if selected_user not in names:
        selected_user = names[0]
    owner = selected_user_record(users_snapshot, selected_user)
    if owner is None or not owner.secrets:
        return selected_user, None
    secret_ids = [secret.id for secret in owner.secrets]
    if selected_secret_id not in secret_ids:
        selected_secret_id = secret_ids[0]
    return selected_user, selected_secret_id


def selected_user_record(users_snapshot: list[UserRecord], selected_user: str | None) -> UserRecord | None:
    """Resolve the currently selected user from the cached snapshot"""
    for user in users_snapshot:
        if user.name == selected_user:
            return user
    return None


def selected_secret_record(owner: UserRecord | None, selected_secret_id: int | None) -> SecretRecord | None:
    """Resolve the currently selected secret from an owner record"""
    if owner is None:
        return None
    for secret in owner.secrets:
        if secret.id == selected_secret_id:
            return secret
    return None


def section_values(current_screen: str) -> tuple[list[str], int]:
    """Return ordered section ids and the currently selected index"""
    normalized_screen = normalize_screen(current_screen)
    return list(SCREEN_ORDER), SCREEN_ORDER.index(normalized_screen)


def user_entries(
    users_snapshot: list[UserRecord],
    selected_user: str | None,
    translate: LabelTranslateFn,
) -> tuple[list[tuple[str, str]], int | None]:
    """Return visible rows and selected index for the users list"""
    items = [(user.name, f"{user.name} [{translate('on' if user.enabled else 'off', 'on' if user.enabled else 'off')}]") for user in users_snapshot]
    names = [user.name for user in users_snapshot]
    index = names.index(selected_user) if selected_user in names else None
    return items, index


def secret_entries(owner: UserRecord | None, selected_secret_id: int | None) -> tuple[list[tuple[int, str]], int | None]:
    """Return visible rows and selected index for the secrets list"""
    if owner is None:
        return [], None
    items = [(secret.id, f"#{secret.id} {secret.note or '-'}") for secret in owner.secrets]
    ids = [secret.id for secret in owner.secrets]
    index = ids.index(selected_secret_id) if selected_secret_id in ids else None
    return items, index
