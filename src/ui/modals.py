"""Reusable modal screens used by the Textual application"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from i18n.en import CATALOG as EN_CATALOG
from i18n.ru import CATALOG as RU_CATALOG
from i18n.zh import CATALOG as ZH_CATALOG
from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual import events
from textual.screen import ModalScreen
from textual.widget import MountError
from textual.widgets import Button, Input, ListView, Static

from models.settings import AppSettings
from ui.theme import (
    ACCENT_LIGHT_BG,
    ACCENT_MID_BG,
    APP_SURFACE,
    BUTTON_DEFAULT_HOVER_BG,
    BUTTON_DANGER_BORDER,
    BUTTON_DANGER_HOVER_BG,
    BUTTON_DANGER_HOVER_BORDER,
    BUTTON_DANGER_TEXT,
    BUTTON_FOCUS_BORDER,
    BUTTON_HEIGHT,
    BUTTON_SUCCESS_HOVER_BG,
    BUTTON_WARNING_BG,
    BUTTON_WARNING_BORDER,
    BUTTON_WARNING_FOCUS_BORDER,
    BUTTON_WARNING_FOCUS_TEXT,
    BUTTON_WARNING_HOVER_BG,
    BUTTON_WARNING_HOVER_BORDER,
    BUTTON_WARNING_TEXT,
    CONTENT_SUBTLE_TEXT,
    DIALOG_BUTTON_WIDTH,
    FOCUS_INK,
    INPUT_BORDER,
    LIST_ROW_EVEN_BG,
    LIST_ROW_ODD_BG,
    MENU_BUTTON_WIDTH,
    SCROLLBAR_SIZE,
    SPLIT_HANDLE_FOCUS_BG,
    SPLIT_HANDLE_FOCUS_COLOR,
    SPLIT_HANDLE_HOVER_BG,
    SPLIT_HANDLE_HOVER_COLOR,
    SPLIT_HANDLE_COLOR,
    THEME_CSS_TOKENS,
    UI_ACCENT_INK,
    UI_BORDER_ACTIVE,
    UI_INK,
    VIEWER_ACTION_BUTTON_WIDTH,
    VIEWER_BG,
    VIEWER_BORDER,
    VIEWER_CLOSE_BG,
    VIEWER_CLOSE_BG_HOVER,
    VIEWER_CLOSE_BORDER_FOCUS,
    VIEWER_FG,
    VIEWER_SCROLLBAR_BG,
    VIEWER_SCROLLBAR_BG_ACTIVE,
    VIEWER_SCROLLBAR_BG_HOVER,
)
from ui.widgets import ValueListItem

WINDOW_TITLE_EMOJI_KEYS = {
    "actions": "⚡",
    "configure": "🔧",
    "source": "📦",
    "manage_telemt": "📦",
    "edit_settings": "🔩",
    "language": "🌍",
    "server": "💻",
    "install_ref_title": "📥",
    "server_logs_title": "📜",
    "server_status_title": "📡",
    "quit_confirm_title": "🚪",
    "add_user": "👤",
    "add_secret": "🔐",
    "delete_user_title": "🚮",
    "delete_secret_title": "🚮",
    "factory_reset": "🚨",
    "export_title": "📤",
    "export": "📤",
}


def _build_window_title_emojis() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for catalog in (EN_CATALOG, RU_CATALOG, ZH_CATALOG):
        for key, emoji in WINDOW_TITLE_EMOJI_KEYS.items():
            title = catalog.get(key)
            if title:
                mapping[title.casefold()] = emoji
    return mapping


WINDOW_TITLE_EMOJIS = _build_window_title_emojis()
TITLE_PREFIX_EMOJIS = frozenset(WINDOW_TITLE_EMOJIS.values()) | {"✨", "👤", "🔐"}


CSS_REPLACEMENTS = {
    "ACCENT_LIGHT_BG": ACCENT_LIGHT_BG,
    "ACCENT_MID_BG": ACCENT_MID_BG,
    "APP_SURFACE": APP_SURFACE,
    "BUTTON_DEFAULT_HOVER_BG": BUTTON_DEFAULT_HOVER_BG,
    "BUTTON_DANGER_BORDER": BUTTON_DANGER_BORDER,
    "BUTTON_DANGER_HOVER_BG": BUTTON_DANGER_HOVER_BG,
    "BUTTON_DANGER_HOVER_BORDER": BUTTON_DANGER_HOVER_BORDER,
    "BUTTON_DANGER_TEXT": BUTTON_DANGER_TEXT,
    "BUTTON_FOCUS_BORDER": BUTTON_FOCUS_BORDER,
    "BUTTON_HEIGHT": BUTTON_HEIGHT,
    "BUTTON_SUCCESS_HOVER_BG": BUTTON_SUCCESS_HOVER_BG,
    "BUTTON_WARNING_BG": BUTTON_WARNING_BG,
    "BUTTON_WARNING_BORDER": BUTTON_WARNING_BORDER,
    "BUTTON_WARNING_FOCUS_BORDER": BUTTON_WARNING_FOCUS_BORDER,
    "BUTTON_WARNING_FOCUS_TEXT": BUTTON_WARNING_FOCUS_TEXT,
    "BUTTON_WARNING_HOVER_BG": BUTTON_WARNING_HOVER_BG,
    "BUTTON_WARNING_HOVER_BORDER": BUTTON_WARNING_HOVER_BORDER,
    "BUTTON_WARNING_TEXT": BUTTON_WARNING_TEXT,
    "CONTENT_SUBTLE_TEXT": CONTENT_SUBTLE_TEXT,
    "DIALOG_BUTTON_WIDTH": DIALOG_BUTTON_WIDTH,
    "FOCUS_INK": FOCUS_INK,
    "INPUT_BORDER": INPUT_BORDER,
    "LIST_ROW_EVEN_BG": LIST_ROW_EVEN_BG,
    "LIST_ROW_ODD_BG": LIST_ROW_ODD_BG,
    "MENU_BUTTON_WIDTH": MENU_BUTTON_WIDTH,
    "SCROLLBAR_SIZE": SCROLLBAR_SIZE,
    "SPLIT_HANDLE_COLOR": SPLIT_HANDLE_COLOR,
    "SPLIT_HANDLE_FOCUS_BG": SPLIT_HANDLE_FOCUS_BG,
    "SPLIT_HANDLE_FOCUS_COLOR": SPLIT_HANDLE_FOCUS_COLOR,
    "SPLIT_HANDLE_HOVER_BG": SPLIT_HANDLE_HOVER_BG,
    "SPLIT_HANDLE_HOVER_COLOR": SPLIT_HANDLE_HOVER_COLOR,
    "UI_ACCENT_INK": UI_ACCENT_INK,
    "UI_BORDER_ACTIVE": UI_BORDER_ACTIVE,
    "VIEWER_ACTION_BUTTON_WIDTH": VIEWER_ACTION_BUTTON_WIDTH,
    "VIEWER_BG": VIEWER_BG,
    "VIEWER_BORDER": VIEWER_BORDER,
    "VIEWER_CLOSE_BG": VIEWER_CLOSE_BG,
    "VIEWER_CLOSE_BG_HOVER": VIEWER_CLOSE_BG_HOVER,
    "VIEWER_CLOSE_BORDER_FOCUS": VIEWER_CLOSE_BORDER_FOCUS,
    "VIEWER_FG": VIEWER_FG,
    "VIEWER_SCROLLBAR_BG": VIEWER_SCROLLBAR_BG,
    "VIEWER_SCROLLBAR_BG_ACTIVE": VIEWER_SCROLLBAR_BG_ACTIVE,
    "VIEWER_SCROLLBAR_BG_HOVER": VIEWER_SCROLLBAR_BG_HOVER,
}


def _css(template: str) -> str:
    for key, value in CSS_REPLACEMENTS.items():
        template = template.replace(f"@@{key}@@", str(value))
    return template


def format_window_title(title: str) -> str:
    """Attach a small context emoji to modal titles when helpful"""
    title = title.strip()
    if not title:
        return title
    title_parts = title.split(maxsplit=1)
    if title_parts and title_parts[0] in TITLE_PREFIX_EMOJIS:
        if len(title_parts) == 1:
            return title_parts[0]
        return f"{title_parts[0]} {title_parts[1].strip()}"
    emoji = WINDOW_TITLE_EMOJIS.get(title.casefold(), "✨")
    return f"{emoji} {title}"


def request_app_quit(screen: ModalScreen[object]) -> None:
    action = getattr(screen.app, "action_quit_app", None)
    if callable(action):
        action()


@dataclass(slots=True)
class ActionSpec:
    key: str
    label: str
    variant: str = "default"
    classes: str = ""


class ConfirmScreen(ModalScreen[bool]):
    CSS = _css(
        THEME_CSS_TOKENS
        + """

    ModalScreen {
        background: $app-surface;
    }

    #confirm-overlay {
        width: 1fr;
        height: 1fr;
        align: center middle;
    }

    #confirm-dialog {
        width: 56;
        max-width: 72;
        min-width: 42;
        height: auto;
        background: $app-surface;
        border: round $ui-border;
        padding: 1 2;
    }

    .dialog-title {
        width: 1fr;
        height: auto;
        content-align: center middle;
        text-align: center;
        text-style: bold;
        color: $ui-accent-ink;
        margin: 0 0 1 0;
        padding: 0 1;
    }

    .dialog-message {
        width: 1fr;
        height: auto;
    }

    .dialog-actions {
        align: center middle;
        margin-top: 1;
        height: auto;
    }

    .dialog-actions Button {
        width: @@DIALOG_BUTTON_WIDTH@@;
        margin: 0 1;
    }

    Button {
        min-width: 9;
        height: @@BUTTON_HEIGHT@@;
        padding: 0 2;
        content-align: center middle;
        text-style: bold;
    }

    .dialog-actions Button.-success {
        background: white;
        color: $ui-ink;
        border: round $ui-border-active;
        text-style: bold;
    }

    .dialog-actions Button.-success:hover {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: $ui-ink;
        border: round @@BUTTON_FOCUS_BORDER@@;
    }

    .dialog-actions Button.-success:focus {
        background: @@BUTTON_DEFAULT_HOVER_BG@@;
        color: $ui-ink;
        border: round @@BUTTON_FOCUS_BORDER@@;
    }

    .dialog-actions Button.-success:hover:focus {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: $ui-ink;
        border: round @@BUTTON_FOCUS_BORDER@@;
    }

    .dialog-actions Button.-error {
        background: white;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_BORDER@@;
        text-style: bold;
    }

    .dialog-actions Button.-error:hover {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    .dialog-actions Button.-error:focus {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: white;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    .dialog-actions Button.-error:hover:focus {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    .dialog-actions Button.-warning {
        background: white;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_BORDER@@;
        text-style: bold;
    }

    .dialog-actions Button.-warning:hover {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    .dialog-actions Button.-warning:focus {
        background: @@BUTTON_WARNING_BORDER@@;
        color: @@BUTTON_WARNING_FOCUS_TEXT@@;
        border: round @@BUTTON_WARNING_FOCUS_BORDER@@;
    }

    .dialog-actions Button.-warning:hover:focus {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    .dialog-message-center {
        width: 1fr;
        content-align: center middle;
        text-align: center;
    }
    """
    )

    def __init__(
        self,
        title: str,
        message: str | Text,
        confirm_label: str = "confirm",
        *,
        cancel_label: str = "cancel",
        confirm_variant: str = "success",
        center_message: bool = False,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.message_text = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.confirm_variant = confirm_variant
        self.center_message = center_message

    def compose(self) -> ComposeResult:
        with Container(id="confirm-overlay"):
            with Container(id="confirm-dialog"):
                yield Static(format_window_title(self.title_text), classes="dialog-title")
                message_classes = "dialog-message dialog-message-center" if self.center_message else "dialog-message"
                yield Static(self.message_text, classes=message_classes)
                with Horizontal(classes="dialog-actions"):
                    yield Button(self.cancel_label, id="cancel")
                    yield Button(self.confirm_label, id="confirm", variant=self.confirm_variant)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def on_mount(self) -> None:
        self.set_focus(None)


FORM_DIALOG_CSS = """
    #confirm-dialog {
        min-width: 28;
        padding: 1 1;
    }

    .form-scroll {
        width: 1fr;
        height: auto;
        background: @@APP_SURFACE@@;
        scrollbar-color: $scrollbar-color;
        scrollbar-color-hover: $scrollbar-color-hover;
        scrollbar-color-active: $scrollbar-color-active;
        scrollbar-background: $scrollbar-background;
        scrollbar-background-hover: $scrollbar-background-hover;
        scrollbar-background-active: $scrollbar-background-active;
        scrollbar-size-vertical: @@SCROLLBAR_SIZE@@;
        scrollbar-size-horizontal: @@SCROLLBAR_SIZE@@;
        padding: 0;
    }

    .form-body {
        width: 1fr;
        height: auto;
        padding: 0 2;
    }

    .form-label {
        width: 1fr;
        height: auto;
    }

    .dialog-actions {
        margin-top: 0;
        padding-top: 1;
    }

    Input {
        width: 1fr;
        margin-top: 1;
        margin-bottom: 1;
    }
"""

FORM_DIALOG_BINDINGS = [
    ("escape", "request_quit", "Quit"),
    ("q", "request_quit", "Quit"),
]


def _modal_viewport_size(screen: ModalScreen[object]) -> tuple[int, int]:
    width = screen.size.width
    height = screen.size.height
    if width > 0 and height > 0:
        return width, height
    try:
        app_size = screen.app.size
    except Exception:
        app_size = None
    if app_size is not None:
        width = app_size.width or width
        height = app_size.height or height
    return max(80, width), max(24, height)


def _wrapped_line_count(text: str, width: int) -> int:
    usable_width = max(1, width)
    return max(1, (cell_len(text) + usable_width - 1) // usable_width)


def _dialog_form_bounds(screen: ModalScreen[object]) -> tuple[int, int]:
    viewport_width, viewport_height = _modal_viewport_size(screen)
    horizontal_margin = max(1, viewport_width // 60)
    vertical_margin = max(horizontal_margin + 1, viewport_height // 50, 1)
    dialog_width = max(28, viewport_width - horizontal_margin * 2)
    title_height = 3
    actions_height = BUTTON_HEIGHT + 1
    chrome_height = 4
    form_height = max(
        BUTTON_HEIGHT + 2,
        viewport_height - vertical_margin * 2 - title_height - actions_height - chrome_height,
    )
    return dialog_width, form_height


def _form_content_width(dialog_width: int) -> int:
    dialog_padding = 2
    form_padding = 4
    return max(12, dialog_width - dialog_padding - form_padding)


class AdaptiveFormDialogMixin:
    def action_request_quit(self) -> None:
        request_app_quit(self)

    def _desired_dialog_width(self, max_dialog_width: int) -> int:
        return max_dialog_width

    def _estimated_form_height(self, dialog_width: int) -> int:
        raise NotImplementedError

    def _layout_metrics(self) -> tuple[int, int]:
        max_dialog_width, max_form_height = _dialog_form_bounds(self)
        dialog_width = min(self._desired_dialog_width(max_dialog_width), max_dialog_width)
        form_height = min(self._estimated_form_height(dialog_width), max_form_height)
        return dialog_width, form_height

    def _apply_form_layout(self) -> None:
        if not getattr(self, "is_mounted", False):
            return
        dialog = self.query_one("#confirm-dialog", Container)
        scroll = self.query_one(".form-scroll", VerticalScroll)
        dialog_width, form_height = self._layout_metrics()
        dialog.styles.width = dialog_width
        scroll.styles.height = form_height


class TextInputScreen(AdaptiveFormDialogMixin, ModalScreen[str | None]):
    CSS = _css(ConfirmScreen.CSS + FORM_DIALOG_CSS)
    BINDINGS = FORM_DIALOG_BINDINGS

    def __init__(
        self,
        title: str,
        label: str,
        *,
        value: str = "",
        password: bool = False,
        save_label: str = "save",
        cancel_label: str = "cancel",
        submit_handler: Callable[[str], bool] | None = None,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.label_text = label
        self.initial_value = value
        self.password = password
        self.save_label = save_label
        self.cancel_label = cancel_label
        self.submit_handler = submit_handler

    def _desired_dialog_width(self, max_dialog_width: int) -> int:
        label_width = cell_len(self.label_text) + 10
        return min(max_dialog_width, max(42, label_width))

    def _estimated_form_height(self, dialog_width: int) -> int:
        label_lines = _wrapped_line_count(self.label_text, _form_content_width(dialog_width))
        return label_lines + BUTTON_HEIGHT + 2

    def compose(self) -> ComposeResult:
        dialog_width, form_height = self._layout_metrics()
        with Container(id="confirm-overlay"):
            with Container(id="confirm-dialog") as dialog:
                dialog.styles.width = dialog_width
                yield Static(format_window_title(self.title_text), classes="dialog-title")
                with VerticalScroll(classes="form-scroll") as scroll:
                    scroll.styles.height = form_height
                    with Vertical(classes="form-body"):
                        yield Static(self.label_text, classes="form-label")
                        yield Input(value=self.initial_value, password=self.password, id="value")
                with Horizontal(classes="dialog-actions"):
                    yield Button(self.cancel_label, id="cancel")
                    yield Button(self.save_label, id="save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        self._submit_current_value()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "value":
            self._submit_current_value()

    def _submit_current_value(self) -> None:
        value = self.query_one("#value", Input).value.strip()
        if self.submit_handler is not None and not self.submit_handler(value):
            return
        self.dismiss(value)

    def on_mount(self) -> None:
        self._apply_form_layout()
        self.query_one("#value", Input).focus()

    def on_resize(self, event: events.Resize) -> None:
        self._apply_form_layout()


class InstallRefScreen(TextInputScreen):
    def _desired_dialog_width(self, max_dialog_width: int) -> int:
        return max_dialog_width


class SettingsScreen(AdaptiveFormDialogMixin, ModalScreen[dict[str, str] | None]):
    CSS = _css(ConfirmScreen.CSS + FORM_DIALOG_CSS)
    BINDINGS = FORM_DIALOG_BINDINGS

    def __init__(
        self,
        settings: AppSettings,
        *,
        title: str = "edit_settings",
        save_label: str = "save",
        cancel_label: str = "cancel",
        mt_port_label: str = "proxy_port",
        stats_port_label: str = "api_port",
        workers_label: str = "workers",
        fake_tls_domain_label: str = "fake_tls_domain",
        ad_tag_label: str = "ad_tag",
    ) -> None:
        super().__init__()
        self.settings = settings
        self.title_text = title
        self.save_label = save_label
        self.cancel_label = cancel_label
        self.mt_port_label = mt_port_label
        self.stats_port_label = stats_port_label
        self.workers_label = workers_label
        self.fake_tls_domain_label = fake_tls_domain_label
        self.ad_tag_label = ad_tag_label

    def _field_labels(self) -> list[str]:
        return [
            self.mt_port_label,
            self.stats_port_label,
            self.workers_label,
            self.fake_tls_domain_label,
            self.ad_tag_label,
        ]

    def _estimated_form_height(self, dialog_width: int) -> int:
        content_width = _form_content_width(dialog_width)
        return sum(
            _wrapped_line_count(label, content_width) + BUTTON_HEIGHT + 2
            for label in self._field_labels()
        )

    def compose(self) -> ComposeResult:
        dialog_width, form_height = self._layout_metrics()
        with Container(id="confirm-overlay"):
            with Container(id="confirm-dialog") as dialog:
                dialog.styles.width = dialog_width
                yield Static(format_window_title(self.title_text), classes="dialog-title")
                with VerticalScroll(classes="form-scroll") as scroll:
                    scroll.styles.height = form_height
                    with Vertical(classes="form-body"):
                        yield Static(self.mt_port_label, classes="form-label")
                        yield Input(str(self.settings.mt_port), id="mt_port", type="integer")
                        yield Static(self.stats_port_label, classes="form-label")
                        yield Input(str(self.settings.stats_port), id="stats_port", type="integer")
                        yield Static(self.workers_label, classes="form-label")
                        yield Input(str(self.settings.workers), id="workers", type="integer")
                        yield Static(self.fake_tls_domain_label, classes="form-label")
                        yield Input(self.settings.fake_tls_domain, id="fake_tls_domain")
                        yield Static(self.ad_tag_label, classes="form-label")
                        yield Input(self.settings.ad_tag, id="ad_tag")
                with Horizontal(classes="dialog-actions"):
                    yield Button(self.cancel_label, id="cancel")
                    yield Button(self.save_label, id="save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        self.dismiss(
            {
                "mt_port": self.query_one("#mt_port", Input).value.strip(),
                "stats_port": self.query_one("#stats_port", Input).value.strip(),
                "workers": self.query_one("#workers", Input).value.strip(),
                "fake_tls_domain": self.query_one("#fake_tls_domain", Input).value.strip(),
                "ad_tag": self.query_one("#ad_tag", Input).value.strip(),
            }
        )

    def on_mount(self) -> None:
        self._apply_form_layout()
        self.query_one("#mt_port", Input).focus()

    def on_resize(self, event: events.Resize) -> None:
        self._apply_form_layout()


class MenuModalScreen(ModalScreen[str | None]):
    CSS = _css(ConfirmScreen.CSS + """
    #confirm-dialog {
        width: 56;
        max-width: 68;
    }

    .menu-actions-scroll {
        width: 1fr;
        height: auto;
        margin-top: 1;
        background: @@APP_SURFACE@@;
        scrollbar-color: $scrollbar-color;
        scrollbar-color-hover: $scrollbar-color-hover;
        scrollbar-color-active: $scrollbar-color-active;
        scrollbar-background: $scrollbar-background;
        scrollbar-background-hover: $scrollbar-background-hover;
        scrollbar-background-active: $scrollbar-background-active;
        scrollbar-size-vertical: @@SCROLLBAR_SIZE@@;
        scrollbar-size-horizontal: @@SCROLLBAR_SIZE@@;
        padding: 0;
    }

    .menu-actions {
        height: auto;
        width: 1fr;
        align: center top;
    }

    ActionMenuScreen.-compact-menu .menu-actions-scroll,
    ServerMenuScreen.-compact-menu .menu-actions-scroll {
        margin-top: 0;
    }

    .menu-button {
        width: @@MENU_BUTTON_WIDTH@@;
        margin-bottom: 1;
        background: white;
        color: @@FOCUS_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    ActionMenuScreen.-compact-menu .menu-button,
    ServerMenuScreen.-compact-menu .menu-button {
        margin-bottom: 0;
    }

    Button.menu-button:hover {
        background: @@BUTTON_DEFAULT_HOVER_BG@@;
        color: @@FOCUS_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
        text-style: bold;
    }

    Button.menu-button:focus {
        background: @@UI_BORDER_ACTIVE@@;
        color: white;
        border: round @@UI_ACCENT_INK@@;
        text-style: bold;
    }

    Button.menu-button:hover:focus {
        background: @@BUTTON_DEFAULT_HOVER_BG@@;
        color: @@FOCUS_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
        text-style: bold;
    }

    Button.menu-button.-success {
        background: white;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.menu-variant-success {
        background: white;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.-success:hover {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.menu-variant-success:hover {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.-success:focus {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.menu-variant-success:focus {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.-success:hover:focus {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.menu-variant-success:hover:focus {
        background: @@BUTTON_SUCCESS_HOVER_BG@@;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
    }

    Button.menu-button.-error {
        background: white;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_BORDER@@;
    }

    Button.menu-button.menu-variant-error {
        background: white;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_BORDER@@;
    }

    Button.menu-button.-error:hover {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.menu-button.menu-variant-error:hover {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.menu-button.-error:focus {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.menu-button.menu-variant-error:focus {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.menu-button.-error:hover:focus {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.menu-button.menu-variant-error:hover:focus {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.menu-button.-warning {
        background: white;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_BORDER@@;
    }

    Button.menu-button.menu-variant-warning {
        background: white;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_BORDER@@;
    }

    Button.menu-button.-warning:hover {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    Button.menu-button.menu-variant-warning:hover {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    Button.menu-button.-warning:focus {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    Button.menu-button.menu-variant-warning:focus {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    Button.menu-button.-warning:hover:focus {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    Button.menu-button.menu-variant-warning:hover:focus {
        background: @@BUTTON_WARNING_BG@@;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_HOVER_BORDER@@;
    }

    ActionMenuScreen.-suppress-initial-highlight Button.menu-button:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.menu-button:focus {
        background: white;
        color: @@FOCUS_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
        text-style: bold;
    }

    ActionMenuScreen.-suppress-initial-highlight Button.menu-button.-success:focus,
    ActionMenuScreen.-suppress-initial-highlight Button.menu-button.menu-variant-success:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.menu-button.-success:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.menu-button.menu-variant-success:focus {
        background: white;
        color: @@UI_ACCENT_INK@@;
        border: round @@UI_BORDER_ACTIVE@@;
        text-style: bold;
    }

    ActionMenuScreen.-suppress-initial-highlight Button.menu-button.-warning:focus,
    ActionMenuScreen.-suppress-initial-highlight Button.menu-button.menu-variant-warning:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.menu-button.-warning:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.menu-button.menu-variant-warning:focus {
        background: white;
        color: @@BUTTON_WARNING_TEXT@@;
        border: round @@BUTTON_WARNING_BORDER@@;
        text-style: bold;
    }

    ActionMenuScreen.-suppress-initial-highlight Button.menu-button.-error:focus,
    ActionMenuScreen.-suppress-initial-highlight Button.menu-button.menu-variant-error:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.menu-button.-error:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.menu-button.menu-variant-error:focus {
        background: white;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_BORDER@@;
        text-style: bold;
    }

    ActionMenuScreen.-suppress-initial-highlight Button.dialog-close:focus,
    ServerMenuScreen.-suppress-initial-highlight Button.dialog-close:focus {
        background: @@VIEWER_CLOSE_BG@@;
        color: @@VIEWER_FG@@;
        border: round @@VIEWER_CLOSE_BG@@;
    }

    Button.dialog-close {
        background: @@VIEWER_CLOSE_BG@@;
        color: @@VIEWER_FG@@;
        border: round @@VIEWER_CLOSE_BG@@;
        text-style: bold;
    }

    Button.dialog-close:hover {
        background: @@VIEWER_CLOSE_BG_HOVER@@;
        border: round @@VIEWER_CLOSE_BG_HOVER@@;
        color: white;
    }

    Button.dialog-close:focus {
        background: @@VIEWER_CLOSE_BG@@;
        color: white;
        border: round @@VIEWER_CLOSE_BORDER_FOCUS@@;
    }
    """)

    BINDINGS = [
        ("up", "focus_prev", "Previous"),
        ("down", "focus_next", "Next"),
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_prev", "Previous"),
        ("escape", "request_quit", "Quit"),
        ("q", "request_quit", "Quit"),
    ]

    def __init__(
        self,
        title: str,
        actions: list[ActionSpec],
        auto_focus_first: bool = False,
        close_label: str = "close",
        *,
        action_handler: Callable[[str], bool] | None = None,
        compact: bool = False,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.actions = actions
        self.auto_focus_first = auto_focus_first
        self.close_label = close_label
        self.action_handler = action_handler
        if compact:
            self.add_class("-compact-menu")

    def compose(self) -> ComposeResult:
        with Container(id="confirm-overlay"):
            with Container(id="confirm-dialog"):
                yield Static(format_window_title(self.title_text), classes="dialog-title")
                with VerticalScroll(classes="menu-actions-scroll"):
                    with Vertical(classes="menu-actions"):
                        for action in self.actions:
                            yield Button(
                                action.label,
                                id=f"menu-{action.key}",
                                variant="default",
                                classes=self._button_classes(action),
                            )
                with Horizontal(classes="dialog-actions"):
                    yield Button(self.close_label, id="cancel", classes="dialog-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id or ""
        if button_id == "cancel":
            self.dismiss(None)
            return
        buttons = self._menu_buttons()
        if event.button not in buttons:
            return
        index = buttons.index(event.button)
        if 0 <= index < len(self.actions):
            self.handle_menu_action(self.actions[index].key)

    def handle_menu_action(self, action: str) -> None:
        if self.action_handler is not None and self.action_handler(action):
            return
        self.dismiss(action)

    def update_actions(self, actions: list[ActionSpec]) -> None:
        self.actions = actions
        buttons = self._menu_buttons()
        if len(buttons) != len(actions):
            return
        focused = self.focused
        focus_index = buttons.index(focused) if focused in buttons else None
        for button, action in zip(buttons, actions, strict=False):
            button.label = action.label
            button.variant = "default"
            button.remove_class("menu-variant-success")
            button.remove_class("menu-variant-warning")
            button.remove_class("menu-variant-error")
            variant_class = self._variant_class_name(action.variant)
            if variant_class is not None:
                button.add_class(variant_class)
        self._sync_menu_layout()
        if focus_index is not None and 0 <= focus_index < len(buttons):
            buttons[focus_index].focus()

    @staticmethod
    def _variant_class_name(variant: str) -> str | None:
        if variant in {"success", "warning", "error"}:
            return f"menu-variant-{variant}"
        return None

    def _button_classes(self, action: ActionSpec) -> str:
        classes = ["menu-button"]
        variant_class = self._variant_class_name(action.variant)
        if variant_class is not None:
            classes.append(variant_class)
        return " ".join(classes)

    def _menu_buttons(self) -> list[Button]:
        return [widget for widget in self.query(".menu-button") if isinstance(widget, Button)]

    def _focusable_buttons(self) -> list[Button]:
        buttons = self._menu_buttons()
        close_button = self.query_one("#cancel", Button)
        return [*buttons, close_button]

    def action_focus_next(self) -> None:
        self.remove_class("-suppress-initial-highlight")
        buttons = self._focusable_buttons()
        if not buttons:
            return
        focused = self.focused
        if focused in buttons:
            index = (buttons.index(focused) + 1) % len(buttons)
        else:
            index = 0
        buttons[index].focus()

    def action_focus_prev(self) -> None:
        self.remove_class("-suppress-initial-highlight")
        buttons = self._focusable_buttons()
        if not buttons:
            return
        focused = self.focused
        if focused in buttons:
            index = (buttons.index(focused) - 1) % len(buttons)
        else:
            index = len(buttons) - 1
        buttons[index].focus()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def action_request_quit(self) -> None:
        request_app_quit(self)

    def _clear_initial_focus(self) -> None:
        self.set_focus(None)

    def _sync_menu_layout(self) -> None:
        if not self.is_mounted:
            return
        dialog = self.query_one("#confirm-dialog", Container)
        actions_scroll = self.query_one(".menu-actions-scroll", VerticalScroll)
        actions_body = self.query_one(".menu-actions", Vertical)
        max_label_width = max((cell_len(action.label) for action in self.actions), default=0)
        button_width = max(MENU_BUTTON_WIDTH, max_label_width + 4)
        available_width = max(24, self.size.width - 6)
        dialog.styles.width = min(button_width + 8, available_width)

        title_block_height = 3
        close_row_height = BUTTON_HEIGHT + 2
        dialog_chrome_height = 4
        content_height = max(
            BUTTON_HEIGHT,
            actions_body.virtual_size.height or actions_body.outer_size.height or len(self.actions) * (BUTTON_HEIGHT + 1),
        )
        available_scroll_height = max(BUTTON_HEIGHT, self.size.height - title_block_height - close_row_height - dialog_chrome_height - 4)
        actions_scroll.styles.height = min(content_height, available_scroll_height)

    def _suspend_focus(self) -> None:
        self.add_class("-suppress-initial-highlight")
        self.set_focus(None)
        self.call_after_refresh(self._clear_initial_focus)

    def reset_interaction_state(self) -> None:
        self._suspend_focus()

    def _resume_button_highlight(self) -> None:
        self.remove_class("-suppress-initial-highlight")

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        if isinstance(event.widget, Button):
            self._resume_button_highlight()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if isinstance(event.widget, Button):
            self._resume_button_highlight()

    def on_mount(self) -> None:
        self._sync_menu_layout()
        if self.auto_focus_first:
            buttons = self._focusable_buttons()
            if buttons:
                buttons[0].focus()
        else:
            self.add_class("-suppress-initial-highlight")

    def on_resize(self, event: events.Resize) -> None:
        self._sync_menu_layout()


class ActionMenuScreen(MenuModalScreen):
    pass


class InlineActionMenuScreen(ActionMenuScreen):
    def handle_menu_action(self, action: str) -> None:
        if self.action_handler is not None and self.action_handler(action):
            self._suspend_focus()
            return
        self.dismiss(action)


class UserConfigureMenuScreen(InlineActionMenuScreen):
    pass


class SourceMenuScreen(InlineActionMenuScreen):
    def handle_menu_action(self, action: str) -> None:
        if self.action_handler is not None and self.action_handler(action):
            return
        self.dismiss(action)


class ServerMenuScreen(MenuModalScreen):
    CSS = MenuModalScreen.CSS
    BINDINGS = MenuModalScreen.BINDINGS

    def __init__(
        self,
        title: str,
        actions: list[ActionSpec],
        *,
        open_status: Callable[[], None],
        open_logs: Callable[[], None],
        action_handler: Callable[[str], bool] | None = None,
        close_label: str = "close",
    ) -> None:
        super().__init__(title, actions, auto_focus_first=False, close_label=close_label, action_handler=action_handler)
        self.open_status = open_status
        self.open_logs = open_logs

    def handle_menu_action(self, action: str) -> None:
        if action == "server_status":
            self._suspend_focus()
            self.open_status()
            return
        if action == "server_logs":
            self._suspend_focus()
            self.open_logs()
            return
        if self.action_handler is not None and self.action_handler(action):
            self._suspend_focus()
            return
        self.dismiss(action)

    def _suspend_focus(self) -> None:
        self.add_class("-suppress-initial-highlight")
        self.set_focus(None)
        self.call_after_refresh(self._clear_initial_focus)

    def on_mount(self) -> None:
        super().on_mount()
        self.set_focus(None)


class FullscreenTextScreen(ModalScreen[str | None]):
    CSS = _css(
        THEME_CSS_TOKENS
        + """

    ModalScreen {
        background: $app-surface;
    }

    #viewer-overlay {
        width: 1fr;
        height: 1fr;
        align: center middle;
    }

    #viewer-dialog {
        width: 1fr;
        height: 1fr;
        margin: 1 2;
        background: $app-surface;
        border: round @@UI_BORDER_ACTIVE@@;
        padding: 1 2;
    }

    #viewer-title {
        width: 1fr;
        content-align: center middle;
        color: @@UI_ACCENT_INK@@;
        text-style: bold;
        margin-bottom: 1;
    }

    #viewer-scroll {
        height: 1fr;
        background: @@VIEWER_BG@@;
        color: @@VIEWER_FG@@;
        border: round @@VIEWER_BORDER@@;
        padding: 0 1;
        margin-bottom: 1;
        scrollbar-color: $scrollbar-color;
        scrollbar-color-hover: $scrollbar-color-hover;
        scrollbar-color-active: $scrollbar-color-active;
        scrollbar-background: @@VIEWER_SCROLLBAR_BG@@;
        scrollbar-background-hover: @@VIEWER_SCROLLBAR_BG_HOVER@@;
        scrollbar-background-active: @@VIEWER_SCROLLBAR_BG_ACTIVE@@;
        scrollbar-size-vertical: @@SCROLLBAR_SIZE@@;
        scrollbar-size-horizontal: @@SCROLLBAR_SIZE@@;
    }

    #viewer-body {
        color: @@VIEWER_FG@@;
        background: @@VIEWER_BG@@;
    }

    #viewer-actions {
        width: 1fr;
        height: auto;
    }

    #viewer-actions-left,
    #viewer-actions-center,
    #viewer-actions-right {
        width: 1fr;
        height: auto;
    }

    #viewer-actions-left {
        align: left middle;
    }

    #viewer-actions-center {
        align: center middle;
    }

    #viewer-actions-right {
        align: right middle;
    }

    #viewer-actions Button {
        width: @@VIEWER_ACTION_BUTTON_WIDTH@@;
        margin: 0 1;
    }

    Button.viewer-danger-action {
        background: white;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_BORDER@@;
        text-style: bold;
    }

    Button.viewer-danger-action:hover {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: @@BUTTON_DANGER_TEXT@@;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.viewer-danger-action:focus {
        background: @@BUTTON_DANGER_HOVER_BG@@;
        color: white;
        border: round @@BUTTON_DANGER_HOVER_BORDER@@;
    }

    Button.viewer-close {
        background: @@VIEWER_CLOSE_BG@@;
        color: @@VIEWER_FG@@;
        border: round @@VIEWER_CLOSE_BG@@;
        text-style: bold;
    }

    Button.viewer-close:hover {
        background: @@VIEWER_CLOSE_BG_HOVER@@;
        color: white;
        border: round @@VIEWER_CLOSE_BG_HOVER@@;
    }

    Button.viewer-close:focus {
        background: @@VIEWER_CLOSE_BG@@;
        color: white;
        border: round @@VIEWER_CLOSE_BORDER_FOCUS@@;
    }
    """
    )

    BINDINGS = [
        ("escape", "request_quit", "Quit"),
        ("q", "request_quit", "Quit"),
        ("up", "scroll_up", "Up"),
        ("down", "scroll_down", "Down"),
        ("pageup", "page_up", "PageUp"),
        ("pagedown", "page_down", "PageDown"),
        ("home", "scroll_home", "Home"),
        ("end", "scroll_end", "End"),
    ]

    def __init__(
        self,
        title: str,
        body: str,
        *,
        return_menu: str | None = None,
        clear_before_close: bool = False,
        actions: list[ActionSpec] | None = None,
        action_handler: Callable[[str], bool] | None = None,
        close_label: str = "close",
    ) -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body
        self.return_menu = return_menu
        self.clear_before_close = clear_before_close
        self.actions = actions or []
        self.action_handler = action_handler
        self.close_label = close_label
        self._close_started = False

    def compose(self) -> ComposeResult:
        with Container(id="viewer-overlay"):
            with Container(id="viewer-dialog"):
                yield Static(format_window_title(self.title_text), id="viewer-title")
                with VerticalScroll(id="viewer-scroll"):
                    yield Static(self.body_text, id="viewer-body")
                with Horizontal(id="viewer-actions"):
                    with Horizontal(id="viewer-actions-left"):
                        for action in self.actions:
                            yield Button(action.label, id=f"viewer-{action.key}", variant=action.variant, classes=action.classes)
                    with Horizontal(id="viewer-actions-center"):
                        yield Button(self.close_label, id="close", classes="viewer-close")
                    yield Static("", id="viewer-actions-right")

    def on_mount(self) -> None:
        self.query_one("#viewer-scroll", VerticalScroll).focus()
        self.query_one("#viewer-scroll", VerticalScroll).scroll_home(animate=False, immediate=True, x_axis=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "close":
            self._close_viewer()
            return
        if button_id.startswith("viewer-"):
            action = button_id.removeprefix("viewer-")
            if self.action_handler is not None and self.action_handler(action):
                return
            self.dismiss(action)

    def action_close_viewer(self) -> None:
        self._close_viewer()

    def action_request_quit(self) -> None:
        request_app_quit(self)

    def _close_viewer(self) -> None:
        if self._close_started:
            return
        self._close_started = True
        if self.clear_before_close:
            body = self.query_one("#viewer-body", Static)
            body.update("")
            self.body_text = ""
            self.call_after_refresh(self._finalize_close)
            return
        self._finalize_close()

    def _finalize_close(self) -> None:
        self.dismiss(self.return_menu)

    def action_scroll_up(self) -> None:
        self.query_one("#viewer-scroll", VerticalScroll).action_scroll_up()

    def action_scroll_down(self) -> None:
        self.query_one("#viewer-scroll", VerticalScroll).action_scroll_down()

    def action_page_up(self) -> None:
        self.query_one("#viewer-scroll", VerticalScroll).scroll_to(y=max(0, self.query_one("#viewer-scroll", VerticalScroll).scroll_y - 10), animate=False, immediate=True)

    def action_page_down(self) -> None:
        scroll = self.query_one("#viewer-scroll", VerticalScroll)
        scroll.scroll_to(y=scroll.scroll_y + 10, animate=False, immediate=True)

    def action_scroll_home(self) -> None:
        self.query_one("#viewer-scroll", VerticalScroll).scroll_home(animate=False, immediate=True, x_axis=False)

    def action_scroll_end(self) -> None:
        self.query_one("#viewer-scroll", VerticalScroll).action_scroll_end()


class InlineCopyAction(Static):
    can_focus = False

    def __init__(self, widget_id: str) -> None:
        super().__init__("", id=widget_id, classes="user-secrets-link-copy")

    async def _on_click(self, event: events.Click) -> None:
        event.stop()
        if self.has_class("-disabled"):
            return
        handler = getattr(self.screen, "copy_secret_link", None)
        if callable(handler):
            handler(self.id or "")


class UserSecretsScreen(ModalScreen[tuple[str, int | None]]):
    MIN_LIST_WIDTH = 20
    MIN_DETAIL_WIDTH = 28

    CSS = _css(
        THEME_CSS_TOKENS
        + """

    ModalScreen {
        background: $app-surface;
    }

    #user-secrets-overlay {
        width: 1fr;
        height: 1fr;
        align: center middle;
    }

    #user-secrets-dialog {
        width: 1fr;
        height: 1fr;
        margin: 1 2;
        background: $app-surface;
        border: round @@UI_BORDER_ACTIVE@@;
        padding: 1 2;
    }

    #user-secrets-header {
        width: 1fr;
        height: auto;
        margin-bottom: 1;
        content-align: center middle;
    }

    #user-secrets-title {
        width: 1fr;
        content-align: center middle;
        text-align: center;
        color: @@UI_ACCENT_INK@@;
        text-style: bold;
    }

    #user-secrets-body {
        height: 1fr;
        margin-bottom: 0;
    }

    #user-secrets-list-column {
        width: 26;
        min-width: 20;
        height: 1fr;
    }

    #user-secrets-detail-column {
        width: 1fr;
        height: 1fr;
    }

    #user-secrets-split-handle {
        width: 1;
        min-width: 1;
        height: 1fr;
        content-align: center middle;
        color: @@SPLIT_HANDLE_COLOR@@;
        background: transparent;
        text-style: bold;
        margin: 0;
        padding: 0;
    }

    #user-secrets-split-handle:hover {
        color: @@SPLIT_HANDLE_HOVER_COLOR@@;
        background: @@SPLIT_HANDLE_HOVER_BG@@;
    }

    #user-secrets-split-handle:focus {
        color: @@SPLIT_HANDLE_FOCUS_COLOR@@;
        background: @@SPLIT_HANDLE_FOCUS_BG@@;
    }

    .user-secrets-panel {
        height: 1fr;
        layout: vertical;
        background: $app-surface;
        border: round $ui-border;
        padding: 1 0 1 1;
    }

    .user-secrets-panel-title {
        width: 1fr;
        content-align: center middle;
        color: @@UI_ACCENT_INK@@;
        text-style: bold;
        margin: 0 0 1 0;
    }

    #user-secrets-list,
    #user-secrets-detail-scroll,
    #user-secrets-list-empty,
    #user-secrets-detail-empty {
        height: 1fr;
        background: $app-surface;
        color: $ui-ink;
        border: none;
        scrollbar-color: $scrollbar-color;
        scrollbar-color-hover: $scrollbar-color-hover;
        scrollbar-color-active: $scrollbar-color-active;
        scrollbar-background: $scrollbar-background;
        scrollbar-background-hover: $scrollbar-background-hover;
        scrollbar-background-active: $scrollbar-background-active;
        scrollbar-size-vertical: @@SCROLLBAR_SIZE@@;
        scrollbar-size-horizontal: @@SCROLLBAR_SIZE@@;
    }

    #user-secrets-list {
        padding: 0 1;
    }

    #user-secrets-list .list-label {
        width: 1fr;
        content-align: center middle;
        text-align: center;
        text-style: bold;
    }

    #user-secrets-list > ListItem {
        background: $app-surface;
        border: round $ui-border;
        color: $ui-ink;
        height: auto;
        min-height: 3;
        padding: 0;
        margin: 0 0 0 0;
    }

    #user-secrets-list > ListItem.-highlight,
    #user-secrets-list:focus > ListItem.-highlight {
        background: transparent;
        color: $ui-ink;
        border: round @@UI_BORDER_ACTIVE@@;
        text-style: bold;
    }

    #user-secrets-list.-active-selection > ListItem.-highlight,
    #user-secrets-list:focus > ListItem.-highlight {
        background: @@ACCENT_LIGHT_BG@@;
        color: $ui-ink;
    }

    #user-secrets-detail-scroll {
        padding: 0;
    }

    #user-secrets-detail {
        color: $ui-ink;
        background: $app-surface;
        width: 1fr;
    }

    .user-secrets-detail-section-title {
        width: 1fr;
        content-align: center middle;
        text-align: center;
        color: @@UI_ACCENT_INK@@;
        text-style: bold;
        margin: 0 0 1 0;
    }

    .user-secrets-detail-section-title.after-section {
        margin: 1 0 1 0;
    }

    .user-secrets-detail-section-body {
        width: 1fr;
        color: $ui-ink;
        background: $app-surface;
        padding: 0 1;
        content-align: center top;
        text-align: center;
    }

    #user-secrets-detail-links {
        width: 1fr;
        height: auto;
        background: $app-surface;
        padding: 0 1;
        align: center top;
    }

    .user-secrets-link-row {
        width: auto;
        height: auto;
        align: left middle;
        margin: 0;
    }

    .user-secrets-link-label {
        width: auto;
        min-width: 0;
        color: $ui-ink;
        text-align: right;
        content-align: right middle;
    }

    .user-secrets-link-copy {
        width: auto;
        min-width: 0;
        max-width: 8;
        height: auto;
        padding: 0;
        margin: 0 0 0 1;
        background: transparent;
        color: #229ED9;
        border: none;
        text-style: bold;
        text-align: left;
        content-align: center middle;
    }

    .user-secrets-link-copy:hover {
        background: transparent;
        color: #168AC0;
        text-style: bold underline;
    }

    .user-secrets-link-copy:focus {
        background: transparent;
        color: #168AC0;
        text-style: bold underline;
    }

    .user-secrets-link-copy.-disabled {
        color: @@BUTTON_DANGER_TEXT@@;
        text-style: none;
    }

    #user-secrets-list-empty,
    #user-secrets-detail-empty {
        display: none;
        padding: 0 4;
        color: @@CONTENT_SUBTLE_TEXT@@;
        content-align: center middle;
        text-align: center;
    }

    #user-secrets-actions {
        width: 1fr;
        height: auto;
        align: center middle;
        min-height: 3;
        background: transparent;
        border: none;
        padding: 1 0;
        margin: 0;
    }

    #user-secrets-actions-left {
        width: auto;
        height: auto;
        align: center middle;
    }

    #user-secrets-actions-left Button {
        width: @@VIEWER_ACTION_BUTTON_WIDTH@@;
        margin: 0 1;
    }

    #user-secrets-actions-left #user-secrets-close-action {
        width: 5;
        min-width: 5;
        max-width: 5;
        height: 3;
        background: white;
        color: $ui-ink;
        border: round $ui-border-active;
        padding: 0;
        margin: 0 1 0 0;
        text-style: bold;
        text-align: center;
        content-align: center middle;
    }

    #user-secrets-actions-left #user-secrets-close-action:hover {
        background: @@BUTTON_DEFAULT_HOVER_BG@@;
        border: round @@BUTTON_FOCUS_BORDER@@;
    }

    #user-secrets-actions-left #user-secrets-close-action:focus {
        background: white;
        border: round @@BUTTON_FOCUS_BORDER@@;
    }
    """
    )

    BINDINGS = [
        ("escape", "request_quit", "Quit"),
        ("q", "request_quit", "Quit"),
    ]

    def __init__(
        self,
        title: str,
        secrets: list[tuple[int, str]],
        *,
        selected_secret_id: int | None,
        detail_provider: Callable[[int | None], tuple[str, str, list[tuple[str, str | None, str | None]]]],
        actions: list[ActionSpec],
        action_handler: Callable[[str, int | None], bool] | None = None,
        secret_enabled_states: dict[int, bool],
        list_title: str,
        detail_title: str,
        credentials_title: str,
        links_title: str,
        enable_label: str = "Enable",
        disable_label: str = "Disable",
        close_label: str = "close",
        none_text: str = "none",
        empty_list_message: str = "",
        empty_detail_message: str = "",
        empty_detail_no_secrets_message: str = "",
        split_hint: str = "",
        no_selection_message: str = "",
    ) -> None:
        super().__init__()
        self.title_text = title
        self.secrets = secrets
        self.selected_secret_id = selected_secret_id
        self.detail_provider = detail_provider
        self.actions = actions
        self.action_handler = action_handler
        self.secret_enabled_states = secret_enabled_states
        self.list_title = list_title
        self.detail_title = detail_title
        self.credentials_title = credentials_title
        self.links_title = links_title
        self.enable_label = enable_label
        self.disable_label = disable_label
        self.close_label = close_label
        self.none_text = none_text
        self.empty_list_message = empty_list_message
        self.empty_detail_message = empty_detail_message
        self.empty_detail_no_secrets_message = empty_detail_no_secrets_message
        self.split_hint = split_hint
        self.no_selection_message = no_selection_message
        self._split_ratio = 0.28
        self._list_active = False
        self._link_targets: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        actions_by_key = {action.key: action for action in self.actions}
        with Container(id="user-secrets-overlay"):
            with Container(id="user-secrets-dialog"):
                with Vertical(id="user-secrets-header"):
                    yield Static(format_window_title(self.title_text), id="user-secrets-title")
                with Horizontal(id="user-secrets-body"):
                    with Vertical(id="user-secrets-list-column"):
                        with Vertical(classes="user-secrets-panel"):
                            yield Static(self.list_title, classes="user-secrets-panel-title")
                            yield Static(self.empty_list_message, id="user-secrets-list-empty")
                            with ListView(id="user-secrets-list", initial_index=None):
                                for secret_id, label in self.secrets:
                                    yield ValueListItem(secret_id, label)
                    yield UserSecretsSplitHandle()
                    with Vertical(id="user-secrets-detail-column"):
                        with Vertical(classes="user-secrets-panel"):
                            yield Static(self.empty_detail_message, id="user-secrets-detail-empty")
                            with VerticalScroll(id="user-secrets-detail-scroll"):
                                yield Static(self.detail_title, classes="user-secrets-detail-section-title")
                                yield Static("", id="user-secrets-detail-overview", classes="user-secrets-detail-section-body")
                                yield Static(self.credentials_title, classes="user-secrets-detail-section-title after-section")
                                yield Static("", id="user-secrets-detail-credentials", classes="user-secrets-detail-section-body")
                                yield Static(self.links_title, classes="user-secrets-detail-section-title after-section")
                                with Vertical(id="user-secrets-detail-links"):
                                    for index in range(3):
                                        with Horizontal(classes="user-secrets-link-row"):
                                            yield Static("", id=f"user-secrets-link-label-{index}", classes="user-secrets-link-label")
                                            yield InlineCopyAction(widget_id=f"user-secrets-link-copy-tg-{index}")
                                            yield InlineCopyAction(widget_id=f"user-secrets-link-copy-tme-{index}")
                with Horizontal(id="user-secrets-actions"):
                    with Horizontal(id="user-secrets-actions-left"):
                        add_action = actions_by_key.get("add_secret")
                        if add_action is not None:
                            yield Button(
                                add_action.label,
                                id=f"user-secrets-action-{add_action.key}",
                                variant=add_action.variant,
                                classes=add_action.classes,
                            )
                        rotate_action = actions_by_key.get("rotate_secret")
                        if rotate_action is not None:
                            rotate_button = Button(
                                rotate_action.label,
                                id=f"user-secrets-action-{rotate_action.key}",
                                variant=rotate_action.variant,
                                classes=rotate_action.classes,
                            )
                            rotate_button.display = False
                            yield rotate_button
                        toggle_button = Button(
                            self.enable_label,
                            id="user-secrets-toggle-action",
                            variant="success",
                        )
                        toggle_button.display = False
                        yield toggle_button
                        delete_action = actions_by_key.get("delete_secret")
                        if delete_action is not None:
                            delete_button = Button(
                                delete_action.label,
                                id=f"user-secrets-action-{delete_action.key}",
                                variant=delete_action.variant,
                                classes=delete_action.classes,
                            )
                            delete_button.display = False
                            yield delete_button
                        yield Button("✖", id="user-secrets-close-action")

    def on_mount(self) -> None:
        secret_ids = [secret_id for secret_id, _ in self.secrets]
        self.query_one("#user-secrets-close-action", Button).tooltip = self.close_label
        self.query_one("#user-secrets-split-handle", UserSecretsSplitHandle).tooltip = self.split_hint
        list_view = self.query_one("#user-secrets-list", ListView)
        self._update_list_state()
        if secret_ids:
            if self.selected_secret_id not in secret_ids:
                self.selected_secret_id = secret_ids[0]
            list_view.index = None
            self._list_active = False
            self.set_focus(None)
        else:
            self.selected_secret_id = None
            list_view.index = None
            self._list_active = False
            self.set_focus(None)
        self._update_detail()
        self.call_after_refresh(self._apply_split)

    def on_resize(self, event: events.Resize) -> None:
        self._apply_split()

    def _apply_split(self) -> None:
        body = self.query_one("#user-secrets-body", Horizontal)
        list_column = self.query_one("#user-secrets-list-column", Vertical)
        handle = self.query_one("#user-secrets-split-handle", UserSecretsSplitHandle)
        total_width = body.size.width or body.content_region.width or max(0, self.size.width - 8)
        if total_width <= 0:
            return
        handle_width = 1
        min_list = self.MIN_LIST_WIDTH
        min_detail = self.MIN_DETAIL_WIDTH
        max_list = max(min_list, total_width - min_detail - handle_width)
        list_width = max(min_list, min(int(total_width * self._split_ratio), max_list))
        list_column.styles.width = list_width
        handle.display = total_width > (min_list + min_detail + handle_width)

    def set_user_secrets_split_from_screen_x(self, screen_x: int) -> None:
        body = self.query_one("#user-secrets-body", Horizontal)
        total_width = body.size.width or body.content_region.width
        if total_width <= 0:
            return
        left = body.region.x
        offset = max(0, min(total_width, screen_x - left))
        self._split_ratio = offset / total_width
        self._apply_split()

    def _update_list_state(self) -> None:
        list_view = self.query_one("#user-secrets-list", ListView)
        empty_state = self.query_one("#user-secrets-list-empty", Static)
        has_secrets = bool(self.secrets)
        list_view.display = has_secrets
        empty_state.display = not has_secrets
        self._update_list_visual_state()

    def _update_list_visual_state(self) -> None:
        list_view = self.query_one("#user-secrets-list", ListView)
        if self._list_active and self.selected_secret_id is not None:
            list_view.add_class("-active-selection")
            return
        list_view.remove_class("-active-selection")

    def _update_detail(self) -> None:
        detail_empty = self.query_one("#user-secrets-detail-empty", Static)
        detail_scroll = self.query_one("#user-secrets-detail-scroll", VerticalScroll)
        if self.selected_secret_id is None or not self._list_active:
            detail_empty.update(self.empty_detail_no_secrets_message if not self.secrets else self.empty_detail_message)
            detail_empty.display = True
            detail_scroll.display = False
            self._clear_links()
            self._update_action_buttons()
            return
        detail_empty.display = False
        detail_scroll.display = True
        overview, credentials, links = self.detail_provider(self.selected_secret_id)
        self.query_one("#user-secrets-detail-overview", Static).update(self._render_detail_fields(overview))
        self.query_one("#user-secrets-detail-credentials", Static).update(
            self._render_detail_fields(credentials, highlight_none_values=True)
        )
        self._update_links(links)
        detail_scroll.scroll_home(animate=False, immediate=True, x_axis=False)
        self._update_action_buttons()

    def _clear_links(self) -> None:
        self._link_targets.clear()
        for index in range(3):
            label = self.query_one(f"#user-secrets-link-label-{index}", Static)
            tg_button = self.query_one(f"#user-secrets-link-copy-tg-{index}", InlineCopyAction)
            tme_button = self.query_one(f"#user-secrets-link-copy-tme-{index}", InlineCopyAction)
            label.update("")
            tg_button.update(Text(""))
            tme_button.update(Text(""))
            tg_button.display = False
            tme_button.display = False
            tg_button.add_class("-disabled")
            tme_button.add_class("-disabled")

    def _update_links(self, links: list[tuple[str, str | None, str | None]]) -> None:
        self._link_targets.clear()
        label_width = max((cell_len(link_label) for link_label, _, _ in links), default=0) + 2
        row_width = self._link_row_width(label_width, links)
        link_rows = list(self.query(".user-secrets-link-row"))
        for index in range(3):
            row = link_rows[index]
            label = self.query_one(f"#user-secrets-link-label-{index}", Static)
            tg_button = self.query_one(f"#user-secrets-link-copy-tg-{index}", InlineCopyAction)
            tme_button = self.query_one(f"#user-secrets-link-copy-tme-{index}", InlineCopyAction)
            row.styles.width = row_width if row_width > 0 else "auto"
            label.styles.width = label_width if label_width > 0 else "auto"
            if index >= len(links):
                label.update("")
                tg_button.update(Text(""))
                tme_button.update(Text(""))
                tg_button.display = False
                tme_button.display = False
                tg_button.add_class("-disabled")
                tme_button.add_class("-disabled")
                continue
            link_label, tg_link, tme_link = links[index]
            label.update(f"{link_label} :")
            tg_button.display = True
            tme_button.display = True
            ee_disabled = link_label == "EE" and not tg_link and not tme_link
            if ee_disabled:
                tg_button.update(Text(self.none_text, style=BUTTON_DANGER_TEXT))
                tme_button.update(Text(""))
                tme_button.display = False
            else:
                tg_button.update(Text("[tg]"))
                tme_button.update(Text("[t.me]"))
            if tg_link:
                tg_button.remove_class("-disabled")
                self._link_targets[tg_button.id or ""] = tg_link
            else:
                tg_button.add_class("-disabled")
            if tme_link:
                tme_button.remove_class("-disabled")
                self._link_targets[tme_button.id or ""] = tme_link
            else:
                tme_button.add_class("-disabled")

    def _link_row_width(self, label_width: int, links: list[tuple[str, str | None, str | None]]) -> int:
        row_width = 0
        for link_label, tg_link, tme_link in links:
            ee_none = link_label == "EE" and not tg_link and not tme_link
            if ee_none:
                content_width = 1 + cell_len(self.none_text)
            else:
                content_width = 1 + cell_len("[tg]") + 1 + cell_len("[t.me]")
            row_width = max(row_width, label_width + content_width)
        return row_width

    def _render_detail_fields(self, body: str, *, highlight_none_values: bool = False) -> Text:
        lines = body.splitlines()
        label_width = max((cell_len(line.split(": ", 1)[0].rstrip()) for line in lines if ": " in line), default=0)
        section_width = 0

        for raw_line in lines:
            line = raw_line.rstrip()
            if not line or ": " not in line:
                continue
            _, value_text = line.split(": ", 1)
            value_style = BUTTON_DANGER_TEXT if highlight_none_values and value_text == self.none_text else UI_INK
            value_renderable = Text(value_text, style=value_style)
            section_width = max(section_width, label_width + 3 + cell_len(value_renderable.plain))

        text = Text()
        for raw_line in lines:
            line = raw_line.rstrip()
            if not line:
                text.append("\n")
                continue
            if ": " in line:
                label_text, value_text = line.split(": ", 1)
                value_style = BUTTON_DANGER_TEXT if highlight_none_values and value_text == self.none_text else UI_INK
                value_renderable = Text(value_text, style=value_style)
                text.append(label_text + (" " * max(0, label_width - cell_len(label_text))), style=UI_INK)
                text.append(" : ", style=UI_INK)
                text.append_text(value_renderable)
                trailing_width = max(0, section_width - (label_width + 3 + cell_len(value_renderable.plain)))
                if trailing_width:
                    text.append(" " * trailing_width, style=UI_INK)
            else:
                text.append(line, style=UI_INK)
            text.append("\n")
        return text

    def _update_action_buttons(self) -> None:
        rotate_button = self.query_one("#user-secrets-action-rotate_secret", Button)
        delete_button = self.query_one("#user-secrets-action-delete_secret", Button)
        toggle_button = self.query_one("#user-secrets-toggle-action", Button)
        secret_enabled = self._selected_secret_enabled()
        has_selected_secret = secret_enabled is not None
        rotate_button.display = has_selected_secret
        delete_button.display = has_selected_secret
        if secret_enabled is None:
            toggle_button.display = False
            return
        toggle_button.display = True
        toggle_button.label = self.disable_label if secret_enabled else self.enable_label
        toggle_button.variant = "error" if secret_enabled else "success"

    @property
    def list_active(self) -> bool:
        return self._list_active

    async def refresh_content(
        self,
        *,
        secrets: list[tuple[int, str]],
        secret_enabled_states: dict[int, bool],
        selected_secret_id: int | None,
        list_active: bool,
    ) -> None:
        list_changed = secrets != self.secrets
        self.secrets = secrets
        self.secret_enabled_states = secret_enabled_states
        secret_ids = [secret_id for secret_id, _ in secrets]
        if selected_secret_id not in secret_ids:
            selected_secret_id = secret_ids[0] if secret_ids else None
        self.selected_secret_id = selected_secret_id
        self._list_active = list_active and self.selected_secret_id is not None

        list_view = self.query_one("#user-secrets-list", ListView)
        if list_changed:
            items = [ValueListItem(secret_id, label) for secret_id, label in secrets]
            try:
                await list_view.clear()
                if items:
                    await list_view.extend(items)
            except MountError:
                return

        if self._list_active and self.selected_secret_id in secret_ids:
            list_view.index = secret_ids.index(self.selected_secret_id)
        else:
            list_view.index = None

        self._update_list_state()
        self._update_detail()

    def _selected_secret_enabled(self) -> bool | None:
        if self.selected_secret_id is None or not self._list_active:
            return None
        return self.secret_enabled_states.get(self.selected_secret_id)

    def _set_selected_secret(self, secret_id: int | None) -> None:
        if self.selected_secret_id == secret_id:
            return
        self.selected_secret_id = secret_id
        self._update_detail()

    def _set_list_active(self, active: bool) -> None:
        active = active and bool(self.secrets)
        if self._list_active == active and (active or not self.secrets):
            return
        self._list_active = active
        list_view = self.query_one("#user-secrets-list", ListView)
        if self._list_active:
            secret_ids = [secret_id for secret_id, _ in self.secrets]
            if self.selected_secret_id in secret_ids:
                list_view.index = secret_ids.index(self.selected_secret_id)
        else:
            list_view.index = None
        self._update_list_visual_state()
        self._update_detail()

    def _clear_transient_focus(self) -> None:
        self.set_focus(None)

    def _release_action_focus(self) -> None:
        self.set_focus(None)
        self.call_after_refresh(self._clear_transient_focus)

    def copy_secret_link(self, action_id: str) -> None:
        link_value = self._link_targets.get(action_id)
        copy_text = getattr(self.app, "_copy_text", None)
        translate = getattr(self.app, "_t", None)
        if link_value and callable(copy_text):
            copy_text(link_value)
            copied_message = translate("copied_to_clipboard", "Copied to clipboard.") if callable(translate) else "Copied to clipboard."
            self.app.notify(copied_message, severity="information")
        self._release_action_focus()

    @staticmethod
    def _is_within(widget: object, ancestor: object) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "parent", None)
        return False

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "user-secrets-list":
            return
        item = event.item
        if isinstance(item, ValueListItem):
            secret_id = int(item.value)
            if self._list_active and self.selected_secret_id == secret_id:
                self._set_list_active(False)
                self.set_focus(None)
                return
            self.selected_secret_id = secret_id
            self._set_list_active(True)
            self._update_detail()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        return

    def on_mouse_down(self, event: events.MouseDown) -> None:
        return

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "user-secrets-close-action":
            self.dismiss(("close", self.selected_secret_id))
            return
        if button_id == "user-secrets-toggle-action":
            if self.selected_secret_id is None or not self._list_active:
                if self.no_selection_message:
                    self.app.notify(self.no_selection_message, severity="warning")
                self._release_action_focus()
                return
            secret_enabled = self.secret_enabled_states.get(self.selected_secret_id)
            action = "disable_secret" if secret_enabled else "enable_secret"
            if self.action_handler is not None and self.action_handler(action, self.selected_secret_id):
                self._release_action_focus()
                return
            self.dismiss((action, self.selected_secret_id))
            return
        if not button_id.startswith("user-secrets-action-"):
            return
        action = button_id.removeprefix("user-secrets-action-")
        if self.action_handler is not None and self.action_handler(action, self.selected_secret_id):
            self._release_action_focus()
            return
        if action != "add_secret" and (self.selected_secret_id is None or not self._list_active):
            if self.no_selection_message:
                self.app.notify(self.no_selection_message, severity="warning")
            self._release_action_focus()
            return
        self.dismiss((action, self.selected_secret_id))

    def action_close_dialog(self) -> None:
        self.dismiss(("close", self.selected_secret_id))

    def action_request_quit(self) -> None:
        request_app_quit(self)


class UserSecretsSplitHandle(Static):
    can_focus = False

    def __init__(self) -> None:
        super().__init__("│", id="user-secrets-split-handle")
        self._dragging = False

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.capture_mouse()
        event.stop()
        if hasattr(self.screen, "set_user_secrets_split_from_screen_x"):
            self.screen.set_user_secrets_split_from_screen_x(int(event.screen_x))

    async def _on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging and hasattr(self.screen, "set_user_secrets_split_from_screen_x"):
            self.screen.set_user_secrets_split_from_screen_x(int(event.screen_x))
            event.stop()

    async def _on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()
            self.screen.set_focus(None)
            event.stop()
