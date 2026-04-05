from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import shutil
import subprocess
import sys
from typing import Any

from rich.cells import cell_len
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, HorizontalScroll, Vertical, VerticalScroll
from textual.widget import MountError
from textual.widgets import Button, Label, ListItem, ListView, Static
from textual.worker import Worker, WorkerState

from controller import AppController, DashboardViewModel
from models.secret import SecretRecord, UserRecord
from ui.actions import (
    action_label,
    configure_actions,
    primary_screen_actions,
    service_actions,
    source_actions,
    split_actions,
    translated_actions,
)
from ui.backend import UIBackend
from ui.dashboard import capture_hardware_snapshot, render_fields, render_status_card
from ui.lists import (
    SCREEN_ORDER,
    normalize_screen,
    refresh_selection,
    screen_menu_label,
    section_values,
    secret_entries,
    selected_secret_record,
    selected_user_record,
    user_entries,
)
from ui.modals import (
    ActionMenuScreen,
    ActionSpec,
    ConfirmScreen,
    FullscreenTextScreen,
    ServiceMenuScreen,
    SettingsScreen,
    TextInputScreen,
)
from ui.state import UIState

BUSY_FRAMES = ("⏳", "⌛")
if sys.platform == "darwin":
    COPY_SELECTION_BINDINGS = [
        Binding("ctrl+c", "copy_selection", "Copy", show=False, priority=True),
        Binding("super+c", "copy_selection", "Copy", show=False, priority=True),
    ]
else:
    COPY_SELECTION_BINDINGS = [
        Binding("ctrl+c", "copy_selection", "Copy", show=False, priority=True),
    ]


@dataclass(slots=True)
class ActionTaskResult:
    output_title: str
    output_body: str
    status_message: str
    severity: str = "information"


class ValueListItem(ListItem):
    def __init__(self, value: str | int, label: str) -> None:
        self.value = value
        self.label_text = label
        super().__init__(Label(label, classes="list-label"))


class SplitHandle(Static):
    def __init__(self) -> None:
        super().__init__("│", id="top-split-handle")
        self._dragging = False

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.capture_mouse()
        event.stop()
        if hasattr(self.app, "set_top_split_from_screen_x"):
            self.app.set_top_split_from_screen_x(int(event.screen_x))

    async def _on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging and hasattr(self.app, "set_top_split_from_screen_x"):
            self.app.set_top_split_from_screen_x(int(event.screen_x))
            event.stop()

    async def _on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()
            event.stop()


class ManagerTextualApp(App[None]):
    CSS = """
    Screen {
        background: #f4fbf6;
        color: #14231a;
    }

    #topbar {
        dock: top;
        height: 3;
        layout: horizontal;
        align: center middle;
        background: #1b4332;
        color: #ffffff;
        padding: 0 1 0 3;
        text-style: bold;
    }

    #topbar-title {
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        color: #ffffff;
        text-style: bold;
    }

    #topbar-close {
        dock: right;
        width: 5;
        min-width: 5;
        height: 3;
        content-align: center middle;
        align: center middle;
        background: #1b4332;
        color: #ffffff;
        border: none;
        padding: 0;
        margin: 0;
        text-style: bold;
    }

    #topbar-close:hover {
        background: #24533d;
        color: white;
        border: round #74c69d;
    }

    #topbar-close:focus {
        background: #24533d;
        color: white;
        border: round #95d5b2;
    }

    #root {
        layout: vertical;
        height: 1fr;
        padding: 1;
    }

    .row {
        layout: horizontal;
        height: 1fr;
    }

    #row-primary {
        min-height: 10;
    }

    #row-secondary {
        min-height: 8;
    }

    #root.compact .row {
        layout: vertical;
        height: auto;
    }

    #sections-panel {
        width: 1fr;
        min-width: 20;
    }

    #overview-panel,
    #activity-panel {
        width: 1fr;
    }

    #top-split-handle {
        width: 1;
        min-width: 1;
        height: 1fr;
        content-align: center middle;
        color: #7aa38d;
        background: transparent;
        text-style: bold;
        margin: 0;
    }

    .panel {
        background: white;
        border: round #cfe8d7;
        padding: 1;
        margin-bottom: 1;
    }

    .panel-title {
        width: 1fr;
        content-align: center middle;
        color: #2d6a4f;
        text-style: bold;
        margin: 0 0 1 0;
    }

    .content-scroll {
        height: 1fr;
    }

    .content-text {
        color: #081c15;
        padding: 0 0 1 0;
    }

    .content-scroll,
    ListView,
    HorizontalScroll {
        scrollbar-color: #8fd3ac;
        scrollbar-color-hover: #74c69d;
        scrollbar-color-active: #2d6a4f;
        scrollbar-background: #f8fcf9;
        scrollbar-background-hover: #f1f8f3;
        scrollbar-background-active: #e7f4ea;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }

    .field-label {
        text-style: bold;
        color: #1b4332;
    }

    ListView {
        background: transparent;
        color: #081c15;
        border: none;
        height: 1fr;
    }

    ListItem {
        background: white;
        color: #081c15;
        padding: 0 1;
        margin-bottom: 1;
    }

    ListItem.-highlight {
        background: #d8f3dc;
        color: #081c15;
        text-style: bold;
    }

    ListView:focus > ListItem.-highlight {
        background: #74c69d;
        color: white;
    }

    .list-label {
        width: 1fr;
    }

    #explorer-lists {
        height: 1fr;
    }

    #users-subpanel,
    #secrets-subpanel {
        width: 1fr;
        height: 1fr;
    }

    .subpanel-title {
        width: 1fr;
        content-align: center middle;
        color: #40916c;
        text-style: bold;
        margin-bottom: 1;
    }

    #activity-panel {
        display: none;
    }

    #actions-panel {
        height: auto;
        min-height: 5;
        padding-bottom: 1;
    }

    #busy-overlay {
        layer: overlay;
        width: 1fr;
        height: 1fr;
        display: none;
        align: center middle;
        background: #edf7f1;
    }

    #busy-dialog {
        width: 26;
        height: auto;
        background: #364152;
        color: #d1d5db;
        border: none;
        padding: 1 2;
    }

    #busy-label {
        width: 1fr;
        color: #d1d5db;
        text-style: none;
        content-align: center middle;
        margin-bottom: 1;
    }

    #busy-progress {
        width: 1fr;
        color: #d1d5db;
        content-align: center middle;
    }

    #actions-scroll {
        height: auto;
    }

    #actions-container {
        width: 1fr;
        height: auto;
        align: center middle;
    }

    .action-button {
        width: auto;
        min-width: 11;
        margin-right: 1;
    }

    Button {
        min-width: 9;
        height: 3;
        padding: 0 2;
        content-align: center middle;
    }

    Button.-style-default {
        background: white;
        color: #081c15;
        border: round #95d5b2;
        text-style: bold;
    }

    Button.-style-default:hover {
        background: #f4fbf6;
    }

    Button.-style-default:focus {
        background: white;
        color: #081c15;
        border: round #52b788;
    }

    Button.-style-default:hover:focus {
        background: #f4fbf6;
        color: #081c15;
        border: round #52b788;
    }

    Button.-success {
        background: #f4fbf6;
        color: #1b4332;
        border: round #74c69d;
        text-style: bold;
    }

    Button.-success:hover {
        background: #eefaf2;
        color: #1b4332;
        border: round #52b788;
    }

    Button.-success:focus {
        background: #74c69d;
        color: white;
        border: round #40916c;
    }

    Button.-success:hover:focus {
        background: #eefaf2;
        color: #1b4332;
        border: round #52b788;
    }

    Button.-error {
        background: #fff5f5;
        color: #a61e4d;
        border: round #f1aeb5;
        text-style: bold;
    }

    Button.-error:hover {
        background: #fff1f2;
        color: #a61e4d;
        border: round #e88997;
    }

    Button.-error:focus {
        background: #e03131;
        color: white;
        border: round #c92a2a;
    }

    Button.-error:hover:focus {
        background: #fff1f2;
        color: #a61e4d;
        border: round #e88997;
    }

    Button.-warning {
        background: #fff9db;
        color: #7c5c00;
        border: round #e9c46a;
        text-style: bold;
    }

    Button.-warning:hover {
        background: #fff4c2;
        color: #7c5c00;
        border: round #e0b84d;
    }

    Button.-warning:focus {
        background: #e9c46a;
        color: #523d00;
        border: round #c99a1d;
    }

    Button.-warning:hover:focus {
        background: #fff4c2;
        color: #7c5c00;
        border: round #e0b84d;
    }

    Button.-flat {
        background: white;
        color: #1b4332;
        border: round #d7ebe0;
        text-style: bold;
    }

    Button.-flat:hover {
        background: #f4fbf6;
    }

    Button.-flat:focus {
        background: white;
        color: #081c15;
        border: round #74c69d;
    }

    #explorer-panel {
        display: none;
    }
    """

    BINDINGS = [
        *COPY_SELECTION_BINDINGS,
        ("q", "quit_app", "Quit"),
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
        ("left", "prev_screen", "Prev"),
        ("right", "next_screen", "Next"),
        ("n", "next_user", "Next user"),
        ("p", "prev_user", "Prev user"),
        ("j", "next_secret", "Next secret"),
        ("k", "prev_secret", "Prev secret"),
    ]
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.state = UIState(
            current_screen="dashboard",
            status_message="",
            selected_user=None,
            selected_secret_id=None,
            output_title="Activity",
            output_body="",
        )
        self.users_snapshot: list[UserRecord] = []
        self.screen_history: list[str] = []
        self._secondary_actions: dict[str, ActionSpec] = {}
        self._busy = False
        self._busy_label = ""
        self._busy_progress = 0
        self._busy_frame_index = 0
        self._busy_timer: Any = None
        self._top_split_ratio = 1 / 3
        self._hardware_snapshot: list[tuple[str, object]] = []
        self._dashboard_snapshot: DashboardViewModel | None = None
        self._refresh_ui_scheduled = False
        self._reopen_screen_after_action: str | None = None
        self._list_snapshots: dict[str, tuple[tuple[tuple[str | int, str], ...], int | None]] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("", id="topbar-title")
            yield Button("✕", id="topbar-close", classes="topbar-close")
        with Vertical(id="root"):
            with Horizontal(id="row-primary", classes="row"):
                with Vertical(classes="panel", id="sections-panel"):
                    yield Static("", classes="panel-title", id="sections-title")
                    yield ListView(id="sections-list")
                yield SplitHandle()
                with Vertical(classes="panel", id="overview-panel"):
                    yield Static("", classes="panel-title", id="overview-title")
                    with VerticalScroll(classes="content-scroll", id="overview-scroll"):
                        yield Static("", id="overview-content", classes="content-text")
            with Horizontal(id="row-secondary", classes="row"):
                with Vertical(classes="panel", id="explorer-panel"):
                    yield Static("", classes="panel-title", id="explorer-title")
                    with Horizontal(id="explorer-lists"):
                        with Vertical(id="users-subpanel"):
                            yield Static("", classes="subpanel-title", id="users-title")
                            yield ListView(id="users-list")
                        with Vertical(id="secrets-subpanel"):
                            yield Static("", classes="subpanel-title", id="secrets-title")
                            yield ListView(id="secrets-list")
                with Vertical(classes="panel", id="activity-panel"):
                    yield Static("", classes="panel-title", id="activity-title")
                    with VerticalScroll(classes="content-scroll", id="activity-scroll"):
                        yield Static("", id="activity-content", classes="content-text")
            with Vertical(classes="panel", id="actions-panel"):
                yield Static("", classes="panel-title", id="actions-title")
                with HorizontalScroll(id="actions-scroll"):
                    yield Horizontal(id="actions-container")
        with Container(id="busy-overlay"):
            with Vertical(id="busy-dialog"):
                yield Static("", id="busy-label")
                yield Static("", id="busy-progress")

    async def on_mount(self) -> None:
        self._capture_hardware_snapshot()
        await self.refresh_ui()
        self._sync_layout_mode(self.size.width)
        self._apply_top_split()
        self.query_one("#sections-list", ListView).focus()

    def on_resize(self, event: events.Resize) -> None:
        self._sync_layout_mode(event.size.width)
        self._apply_top_split()

    def _sync_layout_mode(self, width: int) -> None:
        root = self.query_one("#root", Vertical)
        if width < 95:
            root.add_class("compact")
        else:
            root.remove_class("compact")

    def _section_min_width(self) -> int:
        labels = [self._screen_menu_label(screen) for screen in SCREEN_ORDER]
        return max(22, max(cell_len(label) for label in labels) + 6)

    def _apply_top_split(self) -> None:
        root = self.query_one("#root", Vertical)
        compact = root.has_class("compact")
        handle = self.query_one("#top-split-handle", SplitHandle)
        if compact:
            self.query_one("#sections-panel", Vertical).styles.width = "1fr"
            handle.display = False
            return
        row = self.query_one("#row-primary", Horizontal)
        total_width = max(40, row.size.width)
        handle.display = True
        handle_width = 3
        min_section = self._section_min_width()
        min_overview = 28
        target = int(total_width * self._top_split_ratio)
        max_section = max(min_section, total_width - min_overview - handle_width)
        section_width = max(min_section, min(target, max_section))
        self.query_one("#sections-panel", Vertical).styles.width = section_width

    def set_top_split_from_screen_x(self, screen_x: int) -> None:
        root = self.query_one("#root", Vertical)
        if root.has_class("compact"):
            return
        row = self.query_one("#row-primary", Horizontal)
        total_width = max(40, row.size.width)
        left = row.region.x
        offset = max(0, min(total_width, screen_x - left))
        self._top_split_ratio = offset / total_width
        self._apply_top_split()

    def _t(self, key: str, default: str | None = None) -> str:
        translated = self.controller.translator.tr(key)
        return default if default is not None and translated == key else translated

    def _screen_menu_label(self, screen: str) -> str:
        return screen_menu_label(screen, self._t)

    def _capture_hardware_snapshot(self) -> None:
        self._hardware_snapshot = capture_hardware_snapshot()

    def _update_topbar(self) -> None:
        header = Text()
        header.append(self._t("app_title", "mtp-manager"), style="bold #ffffff")
        self.query_one("#topbar-title", Static).update(header)

    def _configure_actions(self) -> list[ActionSpec]:
        return configure_actions()

    def _source_actions(self) -> list[ActionSpec]:
        return source_actions()

    def _service_actions(self, service_status: str | None = None) -> list[ActionSpec]:
        status = service_status or (self._dashboard_snapshot.service_status if self._dashboard_snapshot else None)
        service_active = (status or self.controller.dashboard().service_status).lower() == "active"
        return service_actions(service_active)

    def _open_screen(self, screen: str, *, push_history: bool = True) -> None:
        screen = normalize_screen(screen)
        if screen == self.state.current_screen:
            return
        if push_history:
            self.screen_history.append(self.state.current_screen)
        self.state.current_screen = screen

    def _get_selected_user(self) -> UserRecord | None:
        return selected_user_record(self.users_snapshot, self.state.selected_user)

    def _get_selected_secret(self, user: UserRecord | None = None) -> SecretRecord | None:
        return selected_secret_record(user or self._get_selected_user(), self.state.selected_secret_id)

    def _refresh_selection(self) -> None:
        self.users_snapshot = self.controller.list_users()
        self.state.selected_user, self.state.selected_secret_id = refresh_selection(
            self.users_snapshot,
            self.state.selected_user,
            self.state.selected_secret_id,
        )

    async def _replace_list(self, list_id: str, items: list[ValueListItem], selected_index: int | None = 0) -> bool:
        list_view = self.query_one(f"#{list_id}", ListView)
        if not list_view.is_attached:
            return False
        normalized_index = None if not items else max(0, min(selected_index or 0, len(items) - 1))
        snapshot = (tuple((item.value, item.label_text) for item in items), normalized_index)
        if self._list_snapshots.get(list_id) == snapshot:
            if list_view.index != normalized_index:
                list_view.index = normalized_index
            return True
        try:
            await list_view.clear()
            if items:
                await list_view.extend(items)
                list_view.index = normalized_index
            else:
                list_view.index = None
        except MountError:
            return False
        self._list_snapshots[list_id] = snapshot
        return True

    async def _replace_actions(self, actions: list[ActionSpec]) -> bool:
        container = self.query_one("#actions-container", Horizontal)
        if not container.is_attached:
            return False
        try:
            await container.remove_children()
        except MountError:
            return False
        primary_actions, secondary_actions = split_actions(actions)
        self._secondary_actions = {action.key: action for action in secondary_actions}
        buttons = [
            Button(
                action_label(action, self._t),
                id=f"action-{action.key}",
                variant=action.variant,
                classes="action-button",
            )
            for action in primary_actions
        ]
        if buttons:
            try:
                await container.mount_all(buttons)
            except MountError:
                return False
        return True

    def _queue_refresh_ui(self) -> None:
        if self._refresh_ui_scheduled:
            return
        self._refresh_ui_scheduled = True
        self.call_after_refresh(self._run_queued_refresh_ui)

    def _run_queued_refresh_ui(self) -> None:
        self._refresh_ui_scheduled = False
        if not self.is_mounted:
            return
        self.run_worker(self.refresh_ui(), exclusive=True)

    def _build_overview_text(self) -> str:
        selected_user = self._get_selected_user()
        if self.state.current_screen == "users":
            if selected_user is None:
                return "No users yet.\n\n" + self._t("use_actions_users")
            return self.controller.selected_detail_text(self.state.selected_user, self.state.selected_secret_id)
        return self._t("service_dashboard_controls")

    def _render_busy_bar(self, progress: float) -> Text:
        width = 18
        filled = max(0, min(width, int((progress / 100) * width)))
        text = Text()
        if filled:
            text.append("▅" * filled, style="#74c69d")
        if filled < width:
            text.append("▁" * (width - filled), style="#5b6777")
        return text

    def _busy_dialog_width(self) -> int:
        label_width = cell_len(f"{BUSY_FRAMES[self._busy_frame_index]} {self._busy_label}")
        content_width = max(18, label_width)
        desired_width = content_width + 4
        available_width = max(26, self.size.width - 6)
        return max(26, min(desired_width, available_width))

    def _set_actions_disabled(self, disabled: bool) -> None:
        for widget in self.query(".action-button"):
            if isinstance(widget, Button):
                widget.disabled = disabled

    def _update_busy_screen(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#busy-dialog", Vertical).styles.width = self._busy_dialog_width()
        self.query_one("#busy-label", Static).update(f"{BUSY_FRAMES[self._busy_frame_index]} {self._busy_label}")
        self.query_one("#busy-progress", Static).update(self._render_busy_bar(self._busy_progress))

    def _set_busy(self, label: str) -> None:
        self._busy = True
        self._busy_label = label
        self._busy_progress = 0
        self._busy_frame_index = 0
        self._set_actions_disabled(True)
        if self.is_mounted:
            self.query_one("#busy-overlay", Container).display = True
        self._update_busy_screen()
        if self._busy_timer is not None:
            self._busy_timer.stop()
        self._busy_timer = self.set_interval(0.05, self._tick_busy_progress)

    def _clear_busy(self) -> None:
        self._busy = False
        self._busy_label = ""
        if self._busy_timer is not None:
            self._busy_timer.stop()
            self._busy_timer = None
        self._busy_progress = 0
        self._busy_frame_index = 0
        self._set_actions_disabled(False)
        if self.is_mounted:
            self.query_one("#busy-overlay", Container).display = False

    def _tick_busy_progress(self) -> None:
        if not self._busy:
            return
        self._busy_frame_index = (self._busy_frame_index + 1) % len(BUSY_FRAMES)
        if self._busy_progress < 70:
            self._busy_progress += 2.5
        elif self._busy_progress < 85:
            self._busy_progress += 0.9
        elif self._busy_progress < 94:
            self._busy_progress += 0.2
        else:
            self._busy_progress = 94
        self._update_busy_screen()

    def _default_focus_target(self) -> ListView:
        if self.state.current_screen == "users":
            return self.query_one("#users-list", ListView)
        return self.query_one("#sections-list", ListView)

    def _restore_default_focus(self) -> None:
        if not self.is_mounted:
            return
        self._default_focus_target().focus()

    def _on_main_workspace(self) -> bool:
        return normalize_screen(self.state.current_screen) in SCREEN_ORDER

    def _run_service_cleanup(self) -> str:
        result = self.controller.service_cleanup()
        self._capture_hardware_snapshot()
        return result

    def _run_clear_service_logs(self) -> str:
        result = self.controller.clear_service_logs()
        self._capture_hardware_snapshot()
        return result

    def _service_logs_actions(self) -> list[ActionSpec]:
        return [
            ActionSpec("clear_service_logs", "Clean", "error", "viewer-danger-action"),
        ]

    def _service_status_actions(self) -> list[ActionSpec]:
        return [
            ActionSpec("copy_service_status", self._t("copy", "Copy")),
        ]

    def _handle_service_status_viewer_action(self, action: str) -> bool:
        if action != "copy_service_status":
            return False
        self._copy_text(self.controller.service_status_text())
        self.notify(self._t("copied_to_clipboard", "Copied to clipboard."), severity="information")
        return True

    def _copy_text(self, text: str) -> None:
        self.copy_to_clipboard(text)
        if sys.platform != "darwin":
            return
        pbcopy = shutil.which("pbcopy")
        if not pbcopy:
            return
        try:
            subprocess.run([pbcopy], input=text.encode("utf-8"), check=False)
        except OSError:
            return

    def _open_service_logs_screen(self) -> None:
        self.push_screen(
            FullscreenTextScreen(
                "Service Logs",
                self.controller.service_logs_text(),
                clear_before_close=True,
                actions=translated_actions(self._service_logs_actions(), self._t),
            ),
            self._handle_service_logs_modal_result,
        )

    def _open_service_status_screen(self) -> None:
        self.push_screen(
            FullscreenTextScreen(
                "Service Status",
                self.controller.service_status_text(),
                actions=translated_actions(self._service_status_actions(), self._t),
                action_handler=self._handle_service_status_viewer_action,
            )
        )

    def _handle_service_logs_modal_result(self, result: str | None) -> None:
        if result == "clear_service_logs":
            self._reopen_screen_after_action = "service_logs"
            self._run_action(
                self._run_clear_service_logs,
                busy_label=f"{self._t('cleanup_logs', 'Cleanup logs')}...",
            )
            return
        if result == "service_cleanup":
            self._reopen_screen_after_action = "service_logs"
            self._run_action(
                self._run_service_cleanup,
                busy_label=f"{self._t('service_cleanup', 'Cleanup')}...",
            )

    async def _refresh_user_selection_view(self, *, refresh_users: bool = False, refresh_secrets: bool = False) -> None:
        self._refresh_selection()
        self.query_one("#overview-content", Static).update(render_fields(self._build_overview_text()))
        self.query_one("#overview-scroll", VerticalScroll).scroll_home(animate=False, immediate=True, x_axis=False)
        if refresh_users:
            user_items, user_index = self._user_items()
            await self._replace_list("users-list", user_items, user_index)
        if refresh_secrets:
            secret_items, secret_index = self._secret_items()
            await self._replace_list("secrets-list", secret_items, secret_index)

    def _section_items(self) -> tuple[list[ValueListItem], int]:
        values, index = section_values(self.state.current_screen)
        items = [ValueListItem(name, self._screen_menu_label(name)) for name in values]
        return items, index

    def _user_items(self) -> tuple[list[ValueListItem], int | None]:
        entries, index = user_entries(self.users_snapshot, self.state.selected_user)
        items = [ValueListItem(value, label) for value, label in entries]
        return items, index

    def _secret_items(self) -> tuple[list[ValueListItem], int | None]:
        entries, index = secret_entries(self._get_selected_user(), self.state.selected_secret_id)
        items = [ValueListItem(value, label) for value, label in entries]
        return items, index

    def _action_specs(self) -> list[ActionSpec]:
        return primary_screen_actions(self.state.current_screen, bool(self.screen_history))

    async def refresh_ui(
        self,
        *,
        refresh_sections: bool = True,
        refresh_user_lists: bool = True,
        refresh_actions: bool = True,
        preserve_focus: bool = False,
    ) -> None:
        if not self.is_mounted:
            return
        focused = self.focused
        self.state.current_screen = normalize_screen(self.state.current_screen)
        self._refresh_selection()
        self._update_topbar()
        dashboard_mode = self.state.current_screen == "dashboard"
        users_mode = self.state.current_screen == "users"
        self._dashboard_snapshot = self.controller.dashboard() if dashboard_mode else None
        self.query_one("#sections-title", Static).update(f"🌱 {self._t('sections')}")
        self.query_one("#overview-title", Static).update(
            f"{'📡' if dashboard_mode else '👤'} "
            f"{self._t('server_status_panel' if dashboard_mode else 'overview')}"
        )
        self.query_one("#explorer-title", Static).update(f"👥 {self._t('users_secrets')}")
        self.query_one("#users-title", Static).update(self._t("users"))
        self.query_one("#secrets-title", Static).update(self._t("secrets"))
        self.query_one("#actions-title", Static).update(f"🧰 {self._t('actions')}")
        self.query_one("#overview-content", Static).update(
            render_status_card(self._dashboard_snapshot, self._hardware_snapshot, self._t)
            if dashboard_mode
            else render_fields(self._build_overview_text())
        )
        self.query_one("#overview-scroll", VerticalScroll).scroll_home(animate=False, immediate=True, x_axis=False)
        activity_title = self.state.output_title if self.state.output_body.strip() else self._t("activity")
        activity_body = self.state.output_body or ""
        self.query_one("#activity-title", Static).update(f"📝 {activity_title}")
        self.query_one("#activity-content", Static).update(activity_body)
        show_user_lists = users_mode
        show_activity_panel = bool(activity_body.strip()) and not self._busy
        self.query_one("#explorer-panel", Vertical).display = show_user_lists
        self.query_one("#activity-panel", Vertical).display = show_activity_panel
        self.query_one("#row-secondary", Horizontal).display = show_user_lists or show_activity_panel
        if show_activity_panel:
            self.query_one("#activity-scroll", VerticalScroll).scroll_home(animate=False, immediate=True, x_axis=False)

        section_items, section_index = self._section_items()
        user_items, user_index = self._user_items()
        secret_items, secret_index = self._secret_items()

        if refresh_sections:
            if not await self._replace_list("sections-list", section_items, section_index):
                self._queue_refresh_ui()
                return
        if refresh_user_lists:
            if not await self._replace_list("users-list", user_items, user_index):
                self._queue_refresh_ui()
                return
            if not await self._replace_list("secrets-list", secret_items, secret_index):
                self._queue_refresh_ui()
                return
        if refresh_actions:
            if not await self._replace_actions(self._action_specs()):
                self._queue_refresh_ui()
                return
        self._apply_top_split()
        if preserve_focus:
            return
        if focused is None or focused not in self.walk_children():
            self._default_focus_target().focus()

    def _set_activity(self, title: str, body: str) -> None:
        self.state.output_title = title
        self.state.output_body = body or ""
        self.run_worker(self.refresh_ui(), exclusive=True)

    def _clear_activity(self) -> None:
        self._set_activity("Activity", "")

    def _notify_result(self, message: str, *, severity: str = "information") -> None:
        self.state.status_message = message
        self.notify(message, severity=severity)

    def _execute_action(
        self,
        fn: Callable[[], object],
        *,
        output_title: str | None = None,
        success_message: str | None = None,
    ) -> ActionTaskResult:
        try:
            result = fn()
        except Exception as exc:
            return ActionTaskResult(self._t("activity"), "", str(exc), "error")

        if output_title is not None:
            if isinstance(result, (AppSettings, UserRecord, SecretRecord)):
                output_body = ""
            else:
                output_body = str(result)
        else:
            output_body = ""

        if success_message:
            status_message = success_message
        elif isinstance(result, str):
            status_message = result
        else:
            status_message = "Action completed."
        return ActionTaskResult(output_title or self._t("activity"), output_body, status_message)

    def _run_action(
        self,
        fn: Callable[[], object],
        *,
        output_title: str | None = None,
        success_message: str | None = None,
        busy_label: str | None = None,
    ) -> None:
        self._set_busy(busy_label or success_message or output_title or self._t("operation_started"))
        self.run_worker(
            lambda: self._execute_action(fn, output_title=output_title, success_message=success_message),
            name="action",
            exclusive=True,
            thread=True,
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "action":
            return
        if event.state == WorkerState.RUNNING:
            return
        if event.state == WorkerState.SUCCESS and event.worker.result is not None:
            result = event.worker.result
            self._busy_progress = 100
            self._update_busy_screen()
            self.state.output_title = result.output_title
            self.state.output_body = result.output_body
            self._notify_result(result.status_message, severity=result.severity)
            self._clear_busy()
            self.run_worker(self.refresh_ui(), exclusive=True)
            if self._reopen_screen_after_action == "service_logs":
                self._reopen_screen_after_action = None
                self.call_after_refresh(self._open_service_logs_screen)
            return
        if event.state == WorkerState.ERROR:
            self._busy_progress = 100
            self._update_busy_screen()
            message = str(event.worker.error or "Action failed.")
            self.state.output_title = self._t("activity")
            self.state.output_body = ""
            self._notify_result(message, severity="error")
            self._clear_busy()
            self._reopen_screen_after_action = None
            self.run_worker(self.refresh_ui(), exclusive=True)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._busy:
            return
        item = event.item
        if not isinstance(item, ValueListItem):
            return
        list_id = event.list_view.id or ""
        if list_id == "sections-list":
            if str(item.value) == "language":
                self._open_language_menu()
                return
            self._open_screen(str(item.value))
            await self.refresh_ui()
            return
        if list_id == "users-list":
            self.state.selected_user = str(item.value)
            await self._refresh_user_selection_view(refresh_secrets=True)
            return
        if list_id == "secrets-list":
            self.state.selected_secret_id = int(item.value)
            await self._refresh_user_selection_view()

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self._busy:
            return
        item = event.item
        if not isinstance(item, ValueListItem):
            return
        list_id = event.list_view.id or ""
        if list_id == "sections-list":
            screen = normalize_screen(str(item.value))
            if screen == "language":
                return
            if screen != self.state.current_screen:
                self._open_screen(screen)
                await self.refresh_ui()
            return
        if list_id == "users-list":
            user_name = str(item.value)
            if user_name != self.state.selected_user:
                self.state.selected_user = user_name
                await self._refresh_user_selection_view(refresh_secrets=True)
            return
        if list_id == "secrets-list":
            secret_id = int(item.value)
            if secret_id != self.state.selected_secret_id:
                self.state.selected_secret_id = secret_id
                await self._refresh_user_selection_view()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._busy:
            return
        button_id = event.button.id or ""
        if button_id == "topbar-close":
            event.stop()
            self._open_quit_confirmation()
            return
        if not button_id.startswith("action-"):
            return
        action = button_id.removeprefix("action-")
        if action != "refresh":
            self._restore_default_focus()
        self._handle_ui_action(action)

    def _handle_ui_action(self, action: str) -> None:
        if action == "back":
            self.run_worker(self.action_go_back(), exclusive=True)
            return
        if action == "configure_menu":
            self._open_configure_menu()
            return
        if action == "source_menu":
            self._open_source_menu()
            return
        if action == "service_menu":
            self._open_service_menu()
            return
        if action == "more":
            overflow = list(self._secondary_actions.values())
            if overflow:
                self.push_screen(
                    ActionMenuScreen(self._t("actions"), translated_actions(overflow, self._t)),
                    self._handle_action_menu,
                )
            return
        if action == "refresh":
            self._capture_hardware_snapshot()
            self.run_worker(
                self.refresh_ui(
                    refresh_sections=False,
                    refresh_actions=False,
                    preserve_focus=True,
                ),
                exclusive=True,
            )
            return
        if action == "edit_settings":
            self.push_screen(SettingsScreen(self.controller.load_settings()), self._handle_settings_screen)
            return
        if action == "show_export":
            self._run_action(
                lambda: self.controller.export_text_for_user(self.state.selected_user),
                output_title="Export",
            )
            return
        if action == "clear_activity":
            self._clear_activity()
            return
        if action == "setup":
            self._run_action(
                self.controller.run_setup,
                busy_label=f"{self._t('setup', 'Setup')}...",
            )
            return
        if action == "initial_setup":
            self._run_action(
                lambda: self.controller.run_setup(source_mode="fresh"),
                busy_label=f"{self._t('setup', 'Setup')}...",
            )
            return
        if action == "update_source":
            self._run_action(
                self.controller.run_update,
                busy_label=f"{self._t('update_source', 'Sync telemt')}...",
            )
            return
        if action == "rebuild":
            self._run_action(
                self.controller.run_rebuild,
                busy_label=f"{self._t('rebuild', 'Reinstall telemt')}...",
            )
            return
        if action == "install_ref":
            current_ref = self.controller.load_settings().telemt_ref
            self.push_screen(
                TextInputScreen(
                    self._t("install_ref_title", "Install telemt ref"),
                    self._t("install_ref_prompt", "Tag or commit (blank = latest)"),
                    value=current_ref,
                ),
                self._handle_install_ref,
            )
            return
        if action == "add_user":
            self.push_screen(TextInputScreen("Add User", "User name"), self._handle_add_user)
            return
        if action == "add_secret":
            if not self.state.selected_user:
                self._notify_result("Select a user to continue.", severity="warning")
                return
            self.push_screen(TextInputScreen("Add Secret", "Note"), self._handle_add_secret)
            return
        if action == "enable_user":
            self._run_action(lambda: self.controller.set_user_enabled(self.state.selected_user or "", True))
            return
        if action == "disable_user":
            self._run_action(lambda: self.controller.set_user_enabled(self.state.selected_user or "", False))
            return
        if action == "rotate_user":
            self._run_action(lambda: self.controller.rotate_user(self.state.selected_user or ""))
            return
        if action == "delete_user":
            if not self.state.selected_user:
                self._notify_result("Select a user to continue.", severity="warning")
                return
            self.push_screen(
                ConfirmScreen(
                    "Delete User",
                    f"Delete user {self.state.selected_user} and all secrets?",
                    "Delete",
                    confirm_variant="error",
                ),
                self._handle_delete_user,
            )
            return
        if action == "enable_secret":
            self._run_secret_action(lambda secret_id: self.controller.set_secret_enabled(secret_id, True))
            return
        if action == "disable_secret":
            self._run_secret_action(lambda secret_id: self.controller.set_secret_enabled(secret_id, False))
            return
        if action == "rotate_secret":
            self._run_secret_action(self.controller.rotate_secret)
            return
        if action == "delete_secret":
            if self.state.selected_secret_id is None:
                self._notify_result("Select a secret to continue.", severity="warning")
                return
            self.push_screen(
                ConfirmScreen(
                    "Delete Secret",
                    f"Delete secret #{self.state.selected_secret_id}?",
                    "Delete",
                    confirm_variant="error",
                ),
                self._handle_delete_secret,
            )
            return
        if action == "export_to_file":
            self._run_action(
                lambda: self.controller.export_selected_user_to_file(self.state.selected_user),
                output_title="Export File",
            )
            return
        if action == "service_start":
            self._run_action(self.controller.service_start)
            return
        if action == "service_stop":
            self._run_action(self.controller.service_stop)
            return
        if action == "service_restart":
            self._run_action(self.controller.service_restart)
            return
        if action == "service_status":
            self.state.output_title = "Activity"
            self.state.output_body = ""
            self.run_worker(self.refresh_ui(), exclusive=True)
            self._open_service_status_screen()
            return
        if action == "service_logs":
            self.state.output_title = "Activity"
            self.state.output_body = ""
            self.run_worker(self.refresh_ui(), exclusive=True)
            self._open_service_logs_screen()
            return
        if action == "service_cleanup":
            self._run_action(
                self._run_service_cleanup,
                busy_label=f"{self._t('service_cleanup', 'Cleanup')}...",
            )
            return
        if action == "factory_reset":
            self.push_screen(
                ConfirmScreen(
                    "Factory Reset",
                    "Stop telemt, remove managed systemd units, configs, binaries, and runtime state?",
                    "Factory Reset",
                    confirm_variant="error",
                ),
                self._handle_factory_reset,
            )
            return
        if action == "lang_en":
            self._change_language("en")
            return
        if action == "lang_ru":
            self._change_language("ru")

    def _handle_action_menu(self, action: str | None) -> None:
        if action is None:
            self.call_after_refresh(self._restore_default_focus)
            return
        if action:
            self._handle_ui_action(action)

    def _open_configure_menu(self) -> None:
        self.push_screen(
            ActionMenuScreen(self._t("configure"), translated_actions(self._configure_actions(), self._t)),
            self._handle_action_menu,
        )

    def _open_service_menu(self) -> None:
        self.push_screen(self._build_service_menu_screen(), self._handle_service_menu_result)

    def _build_service_menu_screen(self) -> ServiceMenuScreen:
        return ServiceMenuScreen(
            self._t("service_control"),
            translated_actions(self._service_actions(self._dashboard_snapshot.service_status if self._dashboard_snapshot else None), self._t),
            open_status=self._open_service_status_screen,
            open_logs=self._open_service_logs_screen,
        )

    def _handle_service_menu_result(self, action: str | None) -> None:
        if action is None:
            self.call_after_refresh(self._restore_default_focus)
            return
        self._handle_ui_action(action)

    def _open_source_menu(self) -> None:
        self.push_screen(
            ActionMenuScreen(self._t("source", "Binary"), translated_actions(self._source_actions(), self._t)),
            self._handle_source_menu_result,
        )

    def _handle_source_menu_result(self, action: str | None) -> None:
        if action is None:
            self._open_configure_menu()
            return
        self._handle_action_menu(action)

    def _open_language_menu(self) -> None:
        actions = [
            ActionSpec("lang_en", self._t("english", "English")),
            ActionSpec("lang_ru", self._t("russian", "Russian")),
        ]
        self.push_screen(ActionMenuScreen(self._t("language"), actions, auto_focus_first=False), self._handle_language_menu)

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
            self._notify_result(str(exc), severity="error")
            self.run_worker(self.refresh_ui(), exclusive=True)
            return
        self.state.output_title = self._t("activity")
        self.state.output_body = ""
        self._notify_result(self._t("language_changed"))
        self.run_worker(self.refresh_ui(), exclusive=True)

    def _run_secret_action(self, action: Callable[[int], object]) -> None:
        if self.state.selected_secret_id is None:
            self._notify_result("Select a secret to continue.", severity="warning")
            return
        self._run_action(lambda: action(self.state.selected_secret_id))

    def _handle_add_user(self, result: str | None) -> None:
        if result:
            self._run_action(lambda: self.controller.add_user(result), success_message=f"User {result} added.")
            return
        self.call_after_refresh(self._restore_default_focus)

    def _handle_add_secret(self, result: str | None) -> None:
        if result is not None and self.state.selected_user:
            self._run_action(
                lambda: self.controller.add_secret(self.state.selected_user or "", result),
                success_message=f"Secret added for {self.state.selected_user}.",
            )
            return
        self.call_after_refresh(self._restore_default_focus)

    def _handle_install_ref(self, result: str | None) -> None:
        if result is None:
            self.call_after_refresh(self._restore_default_focus)
            return
        busy_label = f"Installing {result.strip()}..." if result.strip() else "Installing latest telemt..."
        self._run_action(
            lambda: self.controller.install_telemt_ref(result),
            busy_label=busy_label,
        )

    def _handle_settings_screen(self, result: dict[str, str] | None) -> None:
        if not result:
            self._open_configure_menu()
            return
        def apply_settings() -> str:
            self.controller.update_settings(
                mt_port=int(result["mt_port"]),
                stats_port=int(result["stats_port"]),
                workers=int(result["workers"]),
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
        self.call_after_refresh(self._restore_default_focus)

    def _open_quit_confirmation(self) -> None:
        self.push_screen(
            ConfirmScreen(
                self._t("quit_confirm_title", "Quit"),
                self._t("quit_confirm_message", "Close mtp-manager? Unsaved terminal context in the UI will be lost."),
                self._t("quit_confirm_button", "Quit"),
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

    async def action_go_back(self) -> None:
        if self._on_main_workspace():
            self._open_quit_confirmation()
            return
        if self.screen_history:
            self.state.current_screen = normalize_screen(self.screen_history.pop())
            await self.refresh_ui()
            return
        if self.state.current_screen != "dashboard":
            self.state.current_screen = "dashboard"
            await self.refresh_ui()
            return
        self._open_quit_confirmation()

    def action_quit_app(self) -> None:
        if self._on_main_workspace():
            self._open_quit_confirmation()
            return
        self.exit()

    def action_copy_selection(self) -> None:
        selected_text = self.screen.get_selected_text()
        if selected_text:
            self._copy_text(selected_text)
            self.notify(self._t("copied_to_clipboard", "Copied to clipboard."), severity="information")
            return
        focused = self.screen.focused
        copy_action = getattr(focused, "action_copy", None) if focused is not None else None
        if callable(copy_action):
            copy_action()
            return
        self.notify(self._t("nothing_to_copy", "Nothing selected to copy."), severity="warning")

    async def action_prev_screen(self) -> None:
        current = normalize_screen(self.state.current_screen)
        index = SCREEN_ORDER.index(current)
        self._open_screen(SCREEN_ORDER[(index - 1) % len(SCREEN_ORDER)])
        await self.refresh_ui()

    async def action_next_screen(self) -> None:
        current = normalize_screen(self.state.current_screen)
        index = SCREEN_ORDER.index(current)
        self._open_screen(SCREEN_ORDER[(index + 1) % len(SCREEN_ORDER)])
        await self.refresh_ui()

    async def action_next_user(self) -> None:
        user = self.controller.next_user(self.state.selected_user)
        if user is not None:
            self.state.selected_user = user
            await self.refresh_ui()

    async def action_prev_user(self) -> None:
        user = self.controller.previous_user(self.state.selected_user)
        if user is not None:
            self.state.selected_user = user
            await self.refresh_ui()

    async def action_next_secret(self) -> None:
        secret_id = self.controller.next_secret_id(self.state.selected_user, self.state.selected_secret_id)
        if secret_id is not None:
            self.state.selected_secret_id = secret_id
            await self.refresh_ui()

    async def action_prev_secret(self) -> None:
        secret_id = self.controller.previous_secret_id(self.state.selected_user, self.state.selected_secret_id)
        if secret_id is not None:
            self.state.selected_secret_id = secret_id
            await self.refresh_ui()


class TextualUI(UIBackend):
    def run(self, controller: AppController) -> int:
        app = ManagerTextualApp(controller)
        app.run()
        return 0
