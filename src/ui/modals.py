"""Reusable modal screens used by the Textual application"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from models.settings import AppSettings

WINDOW_TITLE_EMOJIS = {
    "actions": "⚡",
    "configure": "🔩",
    "source": "📦",
    "settings": "🔩",
    "edit settings": "🔩",
    "service": "🔧",
    "service control": "🔧",
    "service logs": "📜",
    "quit": "🚪",
    "выход": "🚪",
    "add user": "👤",
    "add secret": "🔐",
    "delete user": "🗑️",
    "delete secret": "🗑️",
    "factory reset": "🚨",
    "export": "📤",
}


def format_window_title(title: str) -> str:
    """Attach a small context emoji to modal titles when helpful"""
    title = title.strip()
    if not title:
        return title
    if title[0] in "⚡⚙🛠📜👤🔐🗑🚨📤📈":
        return title
    emoji = WINDOW_TITLE_EMOJIS.get(title.casefold(), "✨")
    return f"{emoji} {title}"


@dataclass(slots=True)
class ActionSpec:
    key: str
    label: str
    variant: str = "default"
    classes: str = ""


class ConfirmScreen(ModalScreen[bool]):
    CSS = """
    $app-surface: #ffffff;
    $ui-ink: #1f2937;
    $ui-accent-ink: #275a45;
    $ui-border: #d9e7df;
    $ui-border-active: #96b9a7;

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
        content-align: center middle;
        text-style: bold;
        color: $ui-accent-ink;
        margin: 0 0 1 0;
    }

    .dialog-actions {
        align: center middle;
        margin-top: 1;
        height: auto;
    }

    .dialog-actions Button {
        width: 16;
        margin: 0 1;
    }

    Button {
        min-width: 9;
        height: 3;
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
        background: #eefaf2;
        color: $ui-ink;
        border: round #6f9d86;
    }

    .dialog-actions Button.-success:focus {
        background: #f4fbf6;
        color: $ui-ink;
        border: round #6f9d86;
    }

    .dialog-actions Button.-success:hover:focus {
        background: #eefaf2;
        color: $ui-ink;
        border: round #6f9d86;
    }

    .dialog-actions Button.-error {
        background: white;
        color: #a61e4d;
        border: round #f1aeb5;
        text-style: bold;
    }

    .dialog-actions Button.-error:hover {
        background: #fff5f5;
        color: #a61e4d;
        border: round #e88997;
    }

    .dialog-actions Button.-error:focus {
        background: #e03131;
        color: white;
        border: round #c92a2a;
    }

    .dialog-actions Button.-error:hover:focus {
        background: #fff5f5;
        color: #a61e4d;
        border: round #e88997;
    }

    .dialog-actions Button.-warning {
        background: white;
        color: #7c5c00;
        border: round #e9c46a;
        text-style: bold;
    }

    .dialog-actions Button.-warning:hover {
        background: #fff9db;
        color: #7c5c00;
        border: round #e0b84d;
    }

    .dialog-actions Button.-warning:focus {
        background: #e9c46a;
        color: #523d00;
        border: round #c99a1d;
    }

    .dialog-actions Button.-warning:hover:focus {
        background: #fff9db;
        color: #7c5c00;
        border: round #e0b84d;
    }

    .dialog-message-center {
        width: 1fr;
        content-align: center middle;
        text-align: center;
    }
    """

    def __init__(
        self,
        title: str,
        message: str,
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
                yield Static(self.message_text, classes="dialog-message-center" if self.center_message else "")
                with Horizontal(classes="dialog-actions"):
                    yield Button(self.cancel_label, id="cancel")
                    yield Button(self.confirm_label, id="confirm", variant=self.confirm_variant)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def on_mount(self) -> None:
        self.set_focus(None)


class TextInputScreen(ModalScreen[str | None]):
    CSS = ConfirmScreen.CSS + """
    Input {
        margin-top: 1;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        title: str,
        label: str,
        *,
        value: str = "",
        password: bool = False,
        save_label: str = "save",
        cancel_label: str = "cancel",
    ) -> None:
        super().__init__()
        self.title_text = title
        self.label_text = label
        self.initial_value = value
        self.password = password
        self.save_label = save_label
        self.cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with Container(id="confirm-overlay"):
            with Container(id="confirm-dialog"):
                yield Static(format_window_title(self.title_text), classes="dialog-title")
                yield Static(self.label_text)
                yield Input(value=self.initial_value, password=self.password, id="value")
                with Horizontal(classes="dialog-actions"):
                    yield Button(self.cancel_label, id="cancel")
                    yield Button(self.save_label, id="save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        self.dismiss(self.query_one("#value", Input).value.strip())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "value":
            self.dismiss(event.value.strip())

    def on_mount(self) -> None:
        self.query_one("#value", Input).focus()


class SettingsScreen(ModalScreen[dict[str, str] | None]):
    CSS = ConfirmScreen.CSS + """
    .field-label {
        color: #52796f;
        margin-top: 1;
        margin-bottom: 0;
    }

    Input {
        margin-top: 0;
        margin-bottom: 1;
        background: #ffffff;
        color: #081c15;
        border: round #b7e4c7;
    }

    Input:focus {
        border: round #74c69d;
    }
    """

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

    def compose(self) -> ComposeResult:
        with Container(id="confirm-overlay"):
            with Container(id="confirm-dialog"):
                yield Static(format_window_title(self.title_text), classes="dialog-title")
                yield Static(self.mt_port_label, classes="field-label")
                yield Input(str(self.settings.mt_port), id="mt_port", type="integer")
                yield Static(self.stats_port_label, classes="field-label")
                yield Input(str(self.settings.stats_port), id="stats_port", type="integer")
                yield Static(self.workers_label, classes="field-label")
                yield Input(str(self.settings.workers), id="workers", type="integer")
                yield Static(self.fake_tls_domain_label, classes="field-label")
                yield Input(self.settings.fake_tls_domain, id="fake_tls_domain")
                yield Static(self.ad_tag_label, classes="field-label")
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
        self.query_one("#mt_port", Input).focus()


class MenuModalScreen(ModalScreen[str | None]):
    CSS = ConfirmScreen.CSS + """
    #confirm-dialog {
        width: 56;
        max-width: 68;
    }

    .menu-actions {
        height: auto;
        margin-top: 1;
        align: center top;
    }

    .menu-button {
        width: 28;
        margin-bottom: 1;
        background: white;
        color: #081c15;
        border: round #95d5b2;
    }

    Button.menu-button:hover {
        background: #f4fbf6;
        color: #081c15;
        border: round #74c69d;
        text-style: bold;
    }

    Button.menu-button:focus {
        background: #74c69d;
        color: white;
        border: round #40916c;
        text-style: bold;
    }

    Button.menu-button:hover:focus {
        background: #f4fbf6;
        color: #081c15;
        border: round #74c69d;
        text-style: bold;
    }

    Button.menu-button.-success {
        background: white;
        color: #1b4332;
        border: round #74c69d;
    }

    Button.menu-button.-success:hover {
        background: #eefaf2;
        color: #1b4332;
        border: round #52b788;
    }

    Button.menu-button.-success:focus {
        background: #74c69d;
        color: white;
        border: round #40916c;
    }

    Button.menu-button.-success:hover:focus {
        background: #eefaf2;
        color: #1b4332;
        border: round #52b788;
    }

    Button.menu-button.-error {
        background: white;
        color: #a61e4d;
        border: round #f1aeb5;
    }

    Button.menu-button.-error:hover {
        background: #fff5f5;
        color: #a61e4d;
        border: round #e88997;
    }

    Button.menu-button.-error:focus {
        background: #e03131;
        color: white;
        border: round #c92a2a;
    }

    Button.menu-button.-error:hover:focus {
        background: #fff5f5;
        color: #a61e4d;
        border: round #e88997;
    }

    Button.menu-button.-warning {
        background: white;
        color: #7c5c00;
        border: round #e9c46a;
    }

    Button.menu-button.-warning:hover {
        background: #fff9db;
        color: #7c5c00;
        border: round #e0b84d;
    }

    Button.menu-button.-warning:focus {
        background: #e9c46a;
        color: #523d00;
        border: round #c99a1d;
    }

    Button.menu-button.-warning:hover:focus {
        background: #fff9db;
        color: #7c5c00;
        border: round #e0b84d;
    }

    ActionMenuScreen.-suppress-initial-highlight Button.menu-button:focus,
    ServiceMenuScreen.-suppress-initial-highlight Button.menu-button:focus {
        background: white;
        color: #10231d;
        border: round #95d5b2;
        text-style: bold;
    }

    ActionMenuScreen.-suppress-initial-highlight Button.dialog-close:focus,
    ServiceMenuScreen.-suppress-initial-highlight Button.dialog-close:focus {
        background: #1f1f1f;
        color: #f5f5f5;
        border: round #1f1f1f;
    }

    Button.dialog-close {
        background: #1f1f1f;
        color: #f5f5f5;
        border: round #1f1f1f;
        text-style: bold;
    }

    Button.dialog-close:hover {
        background: #2b2b2b;
        border: round #2b2b2b;
        color: white;
    }

    Button.dialog-close:focus {
        background: #1f1f1f;
        color: white;
        border: round #5a5a5a;
    }
    """

    BINDINGS = [
        ("up", "focus_prev", "Previous"),
        ("down", "focus_next", "Next"),
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_prev", "Previous"),
        ("escape", "dismiss_none", "Close"),
    ]

    def __init__(self, title: str, actions: list[ActionSpec], auto_focus_first: bool = False, close_label: str = "close") -> None:
        super().__init__()
        self.title_text = title
        self.actions = actions
        self.auto_focus_first = auto_focus_first
        self.close_label = close_label

    def compose(self) -> ComposeResult:
        with Container(id="confirm-overlay"):
            with Container(id="confirm-dialog"):
                yield Static(format_window_title(self.title_text), classes="dialog-title")
                with Vertical(classes="menu-actions"):
                    for action in self.actions:
                        yield Button(action.label, id=f"menu-{action.key}", variant=action.variant, classes="menu-button")
                with Horizontal(classes="dialog-actions"):
                    yield Button(self.close_label, id="cancel", classes="dialog-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id or ""
        if button_id == "cancel":
            self.dismiss(None)
            return
        self.handle_menu_action(button_id.removeprefix("menu-"))

    def handle_menu_action(self, action: str) -> None:
        self.dismiss(action)

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

    def _clear_initial_focus(self) -> None:
        self.set_focus(None)

    def on_mount(self) -> None:
        if self.auto_focus_first:
            buttons = self._focusable_buttons()
            if buttons:
                buttons[0].focus()
        else:
            self.add_class("-suppress-initial-highlight")
            self.call_after_refresh(self._clear_initial_focus)


class ActionMenuScreen(MenuModalScreen):
    pass


class ServiceMenuScreen(MenuModalScreen):
    CSS = MenuModalScreen.CSS
    BINDINGS = MenuModalScreen.BINDINGS

    def __init__(
        self,
        title: str,
        actions: list[ActionSpec],
        *,
        open_status: Callable[[], None],
        open_logs: Callable[[], None],
        close_label: str = "close",
    ) -> None:
        super().__init__(title, actions, auto_focus_first=False, close_label=close_label)
        self.open_status = open_status
        self.open_logs = open_logs

    def handle_menu_action(self, action: str) -> None:
        if action == "service_status":
            self._suspend_focus()
            self.open_status()
            return
        if action == "service_logs":
            self._suspend_focus()
            self.open_logs()
            return
        self.dismiss(action)

    def _suspend_focus(self) -> None:
        self.add_class("-suppress-initial-highlight")
        self.set_focus(None)

    def on_mount(self) -> None:
        super().on_mount()
        self.set_focus(None)


class FullscreenTextScreen(ModalScreen[str | None]):
    CSS = """
    $app-surface: #ffffff;

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
        border: round #74c69d;
        padding: 1 2;
    }

    #viewer-title {
        width: 1fr;
        content-align: center middle;
        color: #2d6a4f;
        text-style: bold;
        margin-bottom: 1;
    }

    #viewer-scroll {
        height: 1fr;
        background: #111315;
        color: #f5f7f6;
        border: round #2d3b34;
        padding: 0 1;
        margin-bottom: 1;
        scrollbar-color: #8fd3ac;
        scrollbar-color-hover: #74c69d;
        scrollbar-color-active: #2d6a4f;
        scrollbar-background: #151b18;
        scrollbar-background-hover: #1d2521;
        scrollbar-background-active: #243029;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }

    #viewer-body {
        color: #f5f7f6;
        background: #111315;
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
        width: 18;
        margin: 0 1;
    }

    Button.viewer-danger-action {
        background: white;
        color: #a61e4d;
        border: round #f1aeb5;
        text-style: bold;
    }

    Button.viewer-danger-action:hover {
        background: #fff5f5;
        color: #a61e4d;
        border: round #e88997;
    }

    Button.viewer-danger-action:focus {
        background: #e03131;
        color: white;
        border: round #c92a2a;
    }

    Button.viewer-close {
        background: #1f1f1f;
        color: #f5f5f5;
        border: round #1f1f1f;
        text-style: bold;
    }

    Button.viewer-close:hover {
        background: #2b2b2b;
        color: white;
        border: round #2b2b2b;
    }

    Button.viewer-close:focus {
        background: #1f1f1f;
        color: white;
        border: round #5a5a5a;
    }
    """

    BINDINGS = [
        ("escape", "close_viewer", "Close"),
        ("q", "close_viewer", "Close"),
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
