from __future__ import annotations

from collections.abc import Callable
import shutil
import subprocess
import sys
from typing import Any

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, HorizontalScroll, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import MountError
from textual.widgets import Button, DataTable, Label, ListView, Static
from textual.worker import Worker, WorkerState

from controller import AppController, DashboardViewModel
from models.secret import SecretRecord, UserRecord
from ui.actions import (
    action_label,
    primary_screen_actions,
    split_actions,
)
from ui.app_styles import APP_CSS
from ui.backend import UIBackend
from ui.dashboard import capture_hardware_snapshot, render_fields, render_status_card
import ui.feedback as ui_feedback
from ui.lists import (
    SCREEN_ORDER,
    SECTION_ORDER,
    normalize_screen,
    refresh_selection,
    screen_menu_label,
    secret_list_items,
    section_values,
    secret_entries,
    selected_secret_record,
    selected_user_record,
    user_entries,
)
from ui.modals import (
    ActionSpec,
    ActionMenuScreen,
    ConfirmScreen,
    InstallRefScreen,
    SettingsScreen,
    ServerMenuScreen,
    TextInputScreen,
    UserConfigureMenuScreen,
    UserSecretsScreen,
)
from ui.modal_flow import ModalFlowMixin
from ui.state import UIState
from ui.theme import (
    APP_HEADER_FG,
    MIN_OVERVIEW_WIDTH,
    SECTION_MIN_ICON_WIDTH,
    SECTION_MIN_TEXT_WIDTH,
    SPLIT_HANDLE_WIDTH,
    TOP_ROW_CHROME_WIDTH,
    UI_ACCENT_INK,
)
from ui.widgets import (
    COPY_SELECTION_BINDINGS,
    SplitHandle,
    TopbarClose,
    UsersTable,
    ValueListItem,
)


class ManagerTextualApp(ModalFlowMixin, App[None]):
    DASHBOARD_REFRESH_INTERVAL = 3.0
    TOP_SPLIT_HANDLE_WIDTH = SPLIT_HANDLE_WIDTH
    MIN_OVERVIEW_WIDTH = MIN_OVERVIEW_WIDTH
    TOP_ROW_CHROME_WIDTH = TOP_ROW_CHROME_WIDTH
    MIN_SECTION_TEXT_WIDTH = SECTION_MIN_TEXT_WIDTH
    MIN_SECTION_ICON_WIDTH = SECTION_MIN_ICON_WIDTH

    CSS = APP_CSS

    BINDINGS = [
        *COPY_SELECTION_BINDINGS,
        ("q", "quit_app", "Quit"),
        ("escape", "quit_app", "Quit"),
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
            output_title="",
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
        self._dashboard_refresh_timer: Any = None
        self._top_split_ratio = 1 / 3
        self._hardware_snapshot: list[tuple[str, object]] = []
        self._dashboard_snapshot: DashboardViewModel | None = None
        self._refresh_ui_scheduled = False
        self._reopen_screen_after_action: object | None = None
        self._list_snapshots: dict[str, tuple[tuple[tuple[str | int, str], ...], int | None]] = {}
        self._users_sort_column = "name"
        self._users_sort_reverse = False
        self._users_row_selected = False
        self._users_table_layout_signature: tuple[int, int] | None = None
        self._users_table_resize_timer: Any = None
        self._sections_label_mode = "full"

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("", id="topbar-balance")
            yield Static("", id="topbar-title")
            yield TopbarClose()
        with Vertical(id="root"):
            with Horizontal(id="workspace-row"):
                with Vertical(classes="panel", id="sections-panel"):
                    yield Static("", classes="panel-title", id="sections-title")
                    yield ListView(id="sections-list")
                yield SplitHandle()
                with Vertical(id="content-column"):
                    with Vertical(classes="panel", id="explorer-panel"):
                        yield Static("", classes="panel-title", id="explorer-title")
                        with Horizontal(id="explorer-lists"):
                            with Vertical(id="users-subpanel"):
                                yield Static("", classes="subpanel-title", id="users-title")
                                yield UsersTable(id="users-table", cursor_type="row", zebra_stripes=True, show_row_labels=False, cell_padding=4)
                                yield ListView(id="users-list")
                                yield Static("", id="users-empty-state")
                            with Vertical(id="secrets-subpanel"):
                                yield Static("", classes="subpanel-title", id="secrets-title")
                                yield ListView(id="secrets-list")
                    with Vertical(classes="panel", id="overview-panel"):
                        yield Static("", classes="panel-title", id="overview-title")
                        with VerticalScroll(classes="content-scroll", id="overview-scroll"):
                            yield Static("", id="overview-content", classes="content-text")
                    with Vertical(classes="panel", id="activity-panel"):
                        yield Static("", classes="panel-title", id="activity-title")
                        with VerticalScroll(classes="content-scroll", id="activity-scroll"):
                            yield Static("", id="activity-content", classes="content-text")
            with Vertical(id="actions-panel"):
                with HorizontalScroll(id="actions-scroll"):
                    yield Horizontal(id="actions-container")
        with Container(id="busy-overlay"):
            with Vertical(id="busy-dialog"):
                yield Static("", id="busy-label")
                yield Static("", id="busy-progress")

    async def on_mount(self) -> None:
        self._capture_hardware_snapshot()
        await self.refresh_ui()
        self.screen_change_signal.subscribe(self, self._sync_dashboard_refresh_timer)
        self._sync_dashboard_refresh_timer(self.screen)
        self._sync_layout_mode(self.size.width)
        self._apply_top_split()
        self.call_after_refresh(self._sync_section_item_labels)
        self.set_focus(None)

    def on_unmount(self) -> None:
        self.screen_change_signal.unsubscribe(self)
        self._stop_dashboard_refresh_timer()

    def on_resize(self, event: events.Resize) -> None:
        self._sync_layout_mode(event.size.width)
        self._apply_top_split()
        self.call_after_refresh(self._sync_section_item_labels)
        if self.is_mounted and self.state.current_screen == "users":
            self._schedule_users_table_resize_refresh()

    def _sync_layout_mode(self, width: int) -> None:
        root = self.query_one("#root", Vertical)
        if width < self._top_row_min_width(icon_only=True):
            root.add_class("compact")
            root.remove_class("sections-icons")
        else:
            root.remove_class("compact")

    def _section_min_width(self, *, icon_only: bool = False, short: bool = False) -> int:
        labels = [self._screen_menu_label(screen, icon_only=icon_only, short=short) for screen in SECTION_ORDER]
        minimum = self.MIN_SECTION_ICON_WIDTH if icon_only else self.MIN_SECTION_TEXT_WIDTH
        chrome = 4 if icon_only else 6
        return max(minimum, max(cell_len(label) for label in labels) + chrome)

    def _top_row_min_width(self, *, icon_only: bool = False) -> int:
        return (
            self._section_min_width(icon_only=icon_only)
            + self.MIN_OVERVIEW_WIDTH
            + self.TOP_SPLIT_HANDLE_WIDTH
            + self.TOP_ROW_CHROME_WIDTH
        )

    def _apply_top_split(self) -> None:
        root = self.query_one("#root", Vertical)
        compact = root.has_class("compact")
        handle = self.query_one("#top-split-handle", SplitHandle)
        section_panel = self.query_one("#sections-panel", Vertical)
        if compact:
            section_panel.styles.width = "1fr"
            handle.display = False
            if self._sections_label_mode != "full":
                self._set_sections_label_mode("full")
            return
        row = self.query_one("#workspace-row", Horizontal)
        measured_width = row.size.width or row.content_region.width or max(0, self.size.width - self.TOP_ROW_CHROME_WIDTH)
        total_width = max(40, measured_width)
        handle.display = True
        handle_width = self.TOP_SPLIT_HANDLE_WIDTH
        text_min_section = self._section_min_width(icon_only=False, short=False)
        short_min_section = self._section_min_width(icon_only=False, short=True)
        icon_min_section = self._section_min_width(icon_only=True)
        min_overview = self.MIN_OVERVIEW_WIDTH
        target = int(total_width * self._top_split_ratio)
        mode = "icon" if target < short_min_section else "short" if target < text_min_section else "full"
        if mode != self._sections_label_mode:
            self._set_sections_label_mode(mode)
        min_section = icon_min_section if mode == "icon" else short_min_section if mode == "short" else text_min_section
        max_section = max(min_section, total_width - min_overview - handle_width)
        section_width = max(min_section, min(target, max_section))
        section_panel.styles.width = section_width

    def set_top_split_from_screen_x(self, screen_x: int) -> None:
        root = self.query_one("#root", Vertical)
        if root.has_class("compact"):
            return
        row = self.query_one("#workspace-row", Horizontal)
        total_width = max(40, row.size.width)
        left = row.region.x
        offset = max(0, min(total_width, screen_x - left))
        self._top_split_ratio = offset / total_width
        self._apply_top_split()
        self.call_after_refresh(self._sync_section_item_labels)
        if self.is_mounted and self.state.current_screen == "users":
            self._schedule_users_table_resize_refresh()

    def _t(self, key: str, default: str | None = None) -> str:
        translated = self.controller.translator.tr(key)
        return default if default is not None and translated == key else translated

    def _can_submit_add_user(self, user_name: str) -> bool:
        if self.controller.get_user(user_name) is not None:
            self._notify_result(
                self.controller.present_error(f"user already exists: {user_name}"),
                severity="error",
            )
            return False
        return True

    def _screen_menu_label(self, screen: str, *, icon_only: bool = False, short: bool = False) -> str:
        return screen_menu_label(screen, self._t, icon_only=icon_only, short=short)

    def _set_sections_label_mode(self, mode: str) -> None:
        self._sections_label_mode = mode
        root = self.query_one("#root", Vertical)
        if mode == "icon":
            root.add_class("sections-icons")
        else:
            root.remove_class("sections-icons")
        if not self.is_mounted:
            return
        self.call_after_refresh(self._sync_section_item_labels)

    def _capture_hardware_snapshot(self) -> None:
        self._hardware_snapshot = capture_hardware_snapshot()

    def _stop_dashboard_refresh_timer(self) -> None:
        if self._dashboard_refresh_timer is None:
            return
        self._dashboard_refresh_timer.stop()
        self._dashboard_refresh_timer = None

    def _start_dashboard_refresh_timer(self) -> None:
        if self._dashboard_refresh_timer is not None:
            return
        self._dashboard_refresh_timer = self.set_interval(
            self.DASHBOARD_REFRESH_INTERVAL,
            self._refresh_dashboard_panel,
        )

    def _dashboard_refresh_visible(self, active_screen: object | None = None) -> bool:
        if not self.is_mounted or self.state.current_screen != "dashboard":
            return False
        visible_screen = self.screen if active_screen is None else active_screen
        return not isinstance(visible_screen, ModalScreen)

    def _sync_dashboard_refresh_timer(self, active_screen: object | None = None) -> None:
        if self._dashboard_refresh_visible(active_screen):
            self._start_dashboard_refresh_timer()
            return
        self._stop_dashboard_refresh_timer()

    def _refresh_dashboard_panel(self) -> None:
        if self._busy or not self._dashboard_refresh_visible():
            return
        if not self.query("#overview-content"):
            return
        try:
            dashboard_snapshot = self.controller.dashboard()
            self._capture_hardware_snapshot()
            overview_content = self.query_one("#overview-content", Static)
        except Exception:
            return
        self._dashboard_snapshot = dashboard_snapshot
        overview_content.update(
            render_status_card(self._dashboard_snapshot, self._hardware_snapshot, self._t)
        )

    def _update_topbar(self) -> None:
        header = Text()
        header.append(self._t("app_title", "mtp-manager"), style=f"bold {APP_HEADER_FG}")
        self.query_one("#topbar-title", Static).update(header)

    def _delete_user_confirm_text(self, user_name: str) -> Text:
        template = self._t("delete_user_confirm")
        prefix, placeholder, suffix = template.partition("{user}")
        text = Text(justify="center")
        if placeholder:
            text.append(prefix)
            text.append(user_name, style=f"bold {UI_ACCENT_INK}")
            text.append(suffix)
            return text
        text.append(template)
        text.append(" ")
        text.append(user_name, style=f"bold {UI_ACCENT_INK}")
        return text

    def _delete_secret_confirm_text(self, secret_id: int | None) -> Text:
        secret = self.controller.get_secret(secret_id)
        secret_name = secret.note if secret is not None and secret.note else "-"
        template = self._t("delete_secret_confirm")
        prefix, placeholder, suffix = template.partition("{secret}")
        text = Text(justify="center")
        if placeholder:
            text.append(prefix)
            text.append(secret_name, style=f"bold {UI_ACCENT_INK}")
            text.append(suffix)
            return text
        text.append(template)
        text.append(" ")
        text.append(secret_name, style=f"bold {UI_ACCENT_INK}")
        return text

    def _open_screen(self, screen: str, *, push_history: bool = True) -> None:
        screen = normalize_screen(screen)
        if screen == self.state.current_screen:
            return
        if push_history:
            self.screen_history.append(self.state.current_screen)
        self.state.current_screen = screen

    def _get_selected_user(self) -> UserRecord | None:
        return selected_user_record(self.users_snapshot, self.state.selected_user)

    def _selected_user_for_actions(self) -> str | None:
        user_name = self.state.selected_user
        if not user_name:
            return None
        if self.state.current_screen == "users" and not self._users_row_selected:
            return None
        return user_name

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
                classes=" ".join(part for part in ["action-button", action.classes] if part),
            )
            for action in primary_actions
        ]
        if buttons:
            try:
                await container.mount_all(buttons)
            except MountError:
                return False
        return True

    async def _refresh_action_bar(self) -> None:
        if not await self._replace_actions(self._action_specs()):
            self._queue_refresh_ui()

    async def _refresh_open_user_secrets_screen(self) -> None:
        current_screen = self.screen
        if not isinstance(current_screen, UserSecretsScreen):
            return
        user = self._get_selected_user()
        secret_items = secret_list_items(user)
        await current_screen.refresh_content(
            secrets=secret_items,
            secret_enabled_states={secret.id: secret.enabled for secret in user.secrets} if user else {},
            selected_secret_id=self.state.selected_secret_id,
            list_active=current_screen.list_active,
        )

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

    def _schedule_users_table_resize_refresh(self) -> None:
        if self._users_table_resize_timer is not None:
            self._users_table_resize_timer.stop()
        self._users_table_resize_timer = self.set_timer(0.06, self._run_users_table_resize_refresh)

    def _users_table_current_layout_signature(self) -> tuple[int, int] | None:
        if not self.is_mounted or self.state.current_screen != "users":
            return None
        if not self.query("#users-table"):
            return None
        table = self.query_one("#users-table", UsersTable)
        users_subpanel = self.query_one("#users-subpanel", Vertical)
        return table.current_layout_signature(
            current_screen=self.state.current_screen,
            users_subpanel=users_subpanel,
        )

    def _run_users_table_resize_refresh(self) -> None:
        self._users_table_resize_timer = None
        if not self.is_mounted or self.state.current_screen != "users":
            return
        if not self.query("#users-table"):
            return
        self.run_worker(
            self._refresh_users_table_after_resize(),
            exclusive=True,
        )

    async def _refresh_users_table_after_resize(self) -> None:
        await self.refresh_ui(
            refresh_sections=False,
            refresh_user_lists=True,
            refresh_actions=False,
            preserve_focus=True,
        )
        self.call_after_refresh(self._finalize_users_table_resize_refresh)

    def _finalize_users_table_resize_refresh(self) -> None:
        if not self.is_mounted or self.state.current_screen != "users":
            return
        if not self.query("#users-table"):
            return
        signature = self._users_table_current_layout_signature()
        if signature is not None:
            self._users_table_layout_signature = signature
        self._sync_users_table()

    def _build_overview_text(self) -> str:
        selected_user = self._get_selected_user()
        if self.state.current_screen == "users":
            if selected_user is None:
                return self._t("no_users_yet") + "\n\n" + self._t("use_actions_users")
            return self.controller.selected_user_text(self.state.selected_user)
        if self.state.current_screen == "secrets":
            if selected_user is None:
                return self._t("no_users_yet") + "\n\n" + self._t("use_actions_secrets")
            return self.controller.selected_secret_text(self.state.selected_user, self.state.selected_secret_id)
        return self._t("dashboard_server_controls")

    def _render_busy_bar(self, progress: float) -> Text:
        return ui_feedback.render_busy_bar(progress)

    def _busy_dialog_width(self) -> int:
        return ui_feedback.busy_dialog_width(
            label=self._busy_label,
            frame_index=self._busy_frame_index,
            viewport_width=self.size.width,
        )

    def _set_actions_disabled(self, disabled: bool) -> None:
        buttons = [widget for widget in self.query(".action-button") if isinstance(widget, Button)]
        ui_feedback.set_actions_disabled(buttons, disabled)

    def _update_busy_screen(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#busy-dialog", Vertical).styles.width = self._busy_dialog_width()
        frame = ui_feedback.BUSY_FRAMES[self._busy_frame_index % len(ui_feedback.BUSY_FRAMES)]
        self.query_one("#busy-label", Static).update(f"{frame} {self._busy_label}")
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
        self._busy_frame_index = (self._busy_frame_index + 1) % len(ui_feedback.BUSY_FRAMES)
        if self._busy_progress < 70:
            self._busy_progress += 2.5
        elif self._busy_progress < 85:
            self._busy_progress += 0.9
        elif self._busy_progress < 94:
            self._busy_progress += 0.2
        else:
            self._busy_progress = 94
        self._update_busy_screen()

    def _default_focus_target(self) -> Any:
        if self.state.current_screen == "users":
            if not self.users_snapshot:
                action_buttons = [
                    widget
                    for widget in self.query(".action-button")
                    if isinstance(widget, Button) and widget.display
                ]
                if action_buttons:
                    return action_buttons[0]
                return self.query_one("#sections-list", ListView)
            return self.query_one("#users-table", UsersTable)
        if self.state.current_screen == "secrets":
            return self.query_one("#secrets-list", ListView)
        return self.query_one("#sections-list", ListView)

    def _restore_default_focus(self) -> None:
        if not self.is_mounted:
            return
        self._default_focus_target().focus()

    def _on_main_workspace(self) -> bool:
        return normalize_screen(self.state.current_screen) in SCREEN_ORDER

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
        items = [
            ValueListItem(
                name,
                self._base_section_label(name),
            )
            for name in values
        ]
        return items, index

    def _base_section_label(self, screen: str) -> str:
        return self._screen_menu_label(
            screen,
            icon_only=self._sections_label_mode == "icon",
            short=self._sections_label_mode == "short",
        )

    def _section_item_label(self, screen: str, item: ValueListItem | None = None) -> str:
        label = self._base_section_label(screen)
        if self._sections_label_mode == "icon":
            return label
        if item is None:
            return label
        available_width = item.content_region.width or item.size.width
        if available_width > 0 and cell_len(label) > available_width:
            return self._screen_menu_label(screen, icon_only=True)
        return label

    def _sync_section_item_labels(self) -> None:
        if not self.is_mounted or not self.query("#sections-list"):
            return
        list_view = self.query_one("#sections-list", ListView)
        values, index = section_values(self.state.current_screen)
        items = [item for item in list_view.children if isinstance(item, ValueListItem)]
        if len(items) != len(values):
            return
        labels: list[str] = []
        for item, name in zip(items, values, strict=False):
            label = self._section_item_label(name, item)
            labels.append(label)
            if item.label_text != label:
                item.label_text = label
                item.query_one(Label).update(Text(label, no_wrap=True, overflow="ellipsis"))
        self._list_snapshots["sections-list"] = (
            tuple((value, label) for value, label in zip(values, labels, strict=False)),
            index,
        )

    def _user_items(self) -> tuple[list[ValueListItem], int | None]:
        entries, index = user_entries(self.users_snapshot, self.state.selected_user, self._t)
        items = [ValueListItem(value, label) for value, label in entries]
        return items, index

    def _sorted_users_snapshot(self) -> list[UserRecord]:
        return UsersTable.sorted_users(
            self.users_snapshot,
            sort_column=self._users_sort_column,
            sort_reverse=self._users_sort_reverse,
        )

    def _users_header_text(self, label_key: str, fallback: str, column_key: str) -> Text:
        return UsersTable.header_text(
            self._t,
            sort_column=self._users_sort_column,
            sort_reverse=self._users_sort_reverse,
            label_key=label_key,
            fallback=fallback,
            column_key=column_key,
        )

    def _set_users_table_selection_state(self, table: DataTable) -> None:
        if isinstance(table, UsersTable):
            table.set_selection_state(self._users_row_selected)

    @staticmethod
    def _users_table_cell_text(value: object) -> str:
        return UsersTable.cell_text(value)

    def _apply_users_table_sort(self, table: DataTable) -> None:
        if not isinstance(table, UsersTable) or table.row_count == 0:
            return
        table.apply_sort(
            sort_column=self._users_sort_column,
            sort_reverse=self._users_sort_reverse,
            selected_user=self.state.selected_user,
            row_selected=self._users_row_selected,
            translate=self._t,
        )

    def _sync_users_table(self) -> None:
        table = self.query_one("#users-table", UsersTable)
        if not table.is_attached:
            return

        width_candidates = [
            self.query_one("#users-subpanel", Vertical).content_region.width,
            table.content_region.width,
            self.query_one("#explorer-panel", Vertical).content_region.width,
            self.query_one("#content-column", Vertical).content_region.width,
            self.query_one("#users-subpanel", Vertical).size.width,
            table.size.width,
            self.query_one("#explorer-panel", Vertical).size.width,
            self.query_one("#content-column", Vertical).size.width,
        ]
        panel_width = next((width for width in width_candidates if width and width > 24), 64)
        table_height_candidates = [
            self.query_one("#users-subpanel", Vertical).content_region.height,
            table.content_region.height,
            self.query_one("#users-subpanel", Vertical).size.height,
            table.size.height,
        ]
        panel_height = next((height for height in table_height_candidates if height and height > 0), 0)
        self._users_table_layout_signature = (panel_width, panel_height)
        self.state.selected_user = table.sync_rows(
            users_snapshot=self.users_snapshot,
            selected_user=self.state.selected_user,
            sort_column=self._users_sort_column,
            sort_reverse=self._users_sort_reverse,
            row_selected=self._users_row_selected,
            translate=self._t,
            panel_width=panel_width,
        )

    def _secret_items(self) -> tuple[list[ValueListItem], int | None]:
        entries, index = secret_entries(self._get_selected_user(), self.state.selected_secret_id)
        items = [ValueListItem(value, label) for value, label in entries]
        return items, index

    def _action_specs(self) -> list[ActionSpec]:
        if self.state.current_screen == "users":
            actions = [ActionSpec("add_user", self._t("add", "Add"), "success")]
            if self.users_snapshot and self._users_row_selected and self.state.selected_user:
                actions.extend(
                    [
                        ActionSpec("user_configure", self._t("manage", "Manage")),
                        ActionSpec("delete_user", self._t("delete", "Delete"), "error"),
                    ]
                )
            return actions
        return primary_screen_actions(self.state.current_screen)

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
        self._sync_dashboard_refresh_timer()
        self._refresh_selection()
        self._update_topbar()
        dashboard_mode = self.state.current_screen == "dashboard"
        users_mode = self.state.current_screen in {"users", "secrets"}
        users_screen = self.state.current_screen == "users"
        secrets_screen = self.state.current_screen == "secrets"
        has_users = bool(self.users_snapshot)
        self._dashboard_snapshot = self.controller.dashboard() if dashboard_mode else None
        overview_content = self.query_one("#overview-content", Static)
        overview_scroll = self.query_one("#overview-scroll", VerticalScroll)
        if dashboard_mode:
            overview_content.add_class("dashboard-card")
            overview_scroll.add_class("dashboard-card-scroll")
        else:
            overview_content.remove_class("dashboard-card")
            overview_scroll.remove_class("dashboard-card-scroll")
        self.query_one("#sections-title", Static).update(self._t("sections"))
        self.query_one("#overview-title", Static).update(
            self._t("service_panel" if dashboard_mode else "overview")
        )
        self.query_one("#top-split-handle", SplitHandle).tooltip = self._t(
            "split_resize_hint",
            "Drag to resize panels",
        )
        self.query_one("#topbar-close", TopbarClose).tooltip = self._t(
            "quit_app_hint",
            "Close application",
        )
        self.query_one("#explorer-title", Static).update(
            self._t("users") if users_screen else self._t("secrets") if secrets_screen else self._t("users_secrets")
        )
        users_title = self.query_one("#users-title", Static)
        secrets_title = self.query_one("#secrets-title", Static)
        users_empty_state = self.query_one("#users-empty-state", Static)
        users_table = self.query_one("#users-table", UsersTable)
        users_title.update(self._t("users"))
        self.query_one("#secrets-title", Static).update(self._t("secrets"))
        users_empty_state.update(self._t("no_users_yet"))
        if dashboard_mode:
            overview_content.update(
                render_status_card(self._dashboard_snapshot, self._hardware_snapshot, self._t)
            )
            overview_scroll.scroll_home(animate=False, immediate=True, x_axis=False)
        elif not users_screen:
            overview_content.update(render_fields(self._build_overview_text()))
            overview_scroll.scroll_home(animate=False, immediate=True, x_axis=False)
        activity_title = self.state.output_title if self.state.output_body.strip() else self._t("activity")
        activity_body = self.state.output_body or ""
        self.query_one("#activity-title", Static).update(activity_title)
        self.query_one("#activity-content", Static).update(activity_body)
        show_user_lists = users_mode
        show_activity_panel = bool(activity_body.strip()) and not self._busy
        actions_panel = self.query_one("#actions-panel", Vertical)
        self.query_one("#explorer-panel", Vertical).display = show_user_lists
        self.query_one("#activity-panel", Vertical).display = show_activity_panel
        explorer_panel = self.query_one("#explorer-panel", Vertical)
        overview_panel = self.query_one("#overview-panel", Vertical)
        activity_panel = self.query_one("#activity-panel", Vertical)
        content_column = self.query_one("#content-column", Vertical)
        if dashboard_mode:
            content_column.remove_class("users-only")
            overview_panel.display = True
            overview_panel.styles.height = "1fr"
            explorer_panel.styles.height = "auto"
        elif users_screen:
            content_column.add_class("users-only")
            overview_panel.display = False
            explorer_panel.styles.height = "1fr"
        elif secrets_screen:
            content_column.remove_class("users-only")
            overview_panel.display = True
            explorer_panel.styles.height = 11
            overview_panel.styles.height = "1fr"
        else:
            content_column.remove_class("users-only")
            overview_panel.display = True
            overview_panel.styles.height = "1fr"
            explorer_panel.styles.height = "auto"
        activity_panel.styles.height = "auto"
        users_subpanel = self.query_one("#users-subpanel", Vertical)
        secrets_subpanel = self.query_one("#secrets-subpanel", Vertical)
        users_list = self.query_one("#users-list", ListView)
        if users_screen:
            users_title.display = False
            users_table.display = has_users
            users_list.display = False
            users_empty_state.display = not has_users
            secrets_title.display = False
            users_subpanel.display = True
            users_subpanel.styles.width = "1fr"
            secrets_subpanel.display = False
            secrets_subpanel.styles.width = "1fr"
        elif secrets_screen:
            users_title.display = True
            users_table.display = False
            users_list.display = True
            users_empty_state.display = False
            secrets_title.display = True
            users_subpanel.display = True
            users_subpanel.styles.width = 20
            secrets_subpanel.display = True
            secrets_subpanel.styles.width = "1fr"
        else:
            users_title.display = True
            users_table.display = False
            users_list.display = True
            users_empty_state.display = False
            secrets_title.display = True
            users_subpanel.display = True
            users_subpanel.styles.width = "1fr"
            secrets_subpanel.display = True
            secrets_subpanel.styles.width = "1fr"
        if show_activity_panel:
            self.query_one("#activity-scroll", VerticalScroll).scroll_home(animate=False, immediate=True, x_axis=False)

        section_items, section_index = self._section_items()
        user_items, user_index = self._user_items()
        secret_items, secret_index = self._secret_items()

        if refresh_sections:
            if not await self._replace_list("sections-list", section_items, section_index):
                self._queue_refresh_ui()
                return
            self.call_after_refresh(self._sync_section_item_labels)
        if refresh_user_lists:
            if users_screen:
                if has_users:
                    self._sync_users_table()
            else:
                if not await self._replace_list("users-list", user_items, user_index):
                    self._queue_refresh_ui()
                    return
            if not await self._replace_list("secrets-list", secret_items, secret_index):
                self._queue_refresh_ui()
                return
        actions = self._action_specs()
        actions_panel.display = bool(actions)
        if refresh_actions:
            if not await self._replace_actions(actions):
                self._queue_refresh_ui()
                return
        if isinstance(self.screen, UserSecretsScreen):
            await self._refresh_open_user_secrets_screen()
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
        self._set_activity(self._t("activity"), "")

    def _notify_result(self, message: str, *, severity: str = "information") -> None:
        ui_feedback.notify_result(self.state, self.notify, message, severity=severity)

    def _execute_action(
        self,
        fn: Callable[[], object],
        *,
        output_title: str | None = None,
        success_message: str | None = None,
    ) -> ui_feedback.ActionTaskResult:
        return ui_feedback.execute_action(
            fn,
            translate=self._t,
            present_error=self.controller.present_error,
            output_title=output_title,
            success_message=success_message,
        )

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

    def _reopen_followup_screen(self, reopen_after_action: object) -> bool:
        if reopen_after_action == "server_logs":
            self.call_after_refresh(self._open_server_logs_screen)
            return True
        if reopen_after_action == "configure_menu":
            self._open_configure_menu()
            return True
        if reopen_after_action == "source_menu":
            self._open_source_menu()
            return True
        if isinstance(reopen_after_action, tuple) and len(reopen_after_action) == 3 and reopen_after_action[0] == "user_secrets":
            _, user_name, secret_id = reopen_after_action

            def reopen_user_secrets() -> None:
                if isinstance(user_name, str):
                    self.state.selected_user = user_name
                self.state.selected_secret_id = secret_id if isinstance(secret_id, int) else None
                self._open_user_secrets_screen(selected_secret_id=self.state.selected_secret_id)

            self.call_after_refresh(reopen_user_secrets)
            return True
        return False

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
            reopen_after_action = self._reopen_screen_after_action
            self._reopen_screen_after_action = None
            if reopen_after_action in {"source_menu", "configure_menu"}:
                if reopen_after_action == "source_menu":
                    self._open_source_menu()
                else:
                    self._open_configure_menu()
                reopen_after_action = None
            self.run_worker(self.refresh_ui(), exclusive=True)
            if isinstance(self.screen, UserConfigureMenuScreen):
                self.call_after_refresh(self._refresh_open_user_configure_menu)
            if isinstance(self.screen, ServerMenuScreen):
                self.call_after_refresh(self._refresh_open_server_menu)
            self._clear_busy()
            if self._reopen_followup_screen(reopen_after_action):
                return
            return
        if event.state == WorkerState.ERROR:
            self._busy_progress = 100
            self._update_busy_screen()
            message = self.controller.present_error(str(event.worker.error or self._t("action_failed")))
            self.state.output_title = self._t("activity")
            self.state.output_body = ""
            self._notify_result(message, severity="error")
            reopen_after_action = self._reopen_screen_after_action
            self._reopen_screen_after_action = None
            if reopen_after_action in {"source_menu", "configure_menu"}:
                if reopen_after_action == "source_menu":
                    self._open_source_menu()
                else:
                    self._open_configure_menu()
                reopen_after_action = None
            self.run_worker(self.refresh_ui(), exclusive=True)
            if isinstance(self.screen, UserConfigureMenuScreen):
                self.call_after_refresh(self._refresh_open_user_configure_menu)
            if isinstance(self.screen, ServerMenuScreen):
                self.call_after_refresh(self._refresh_open_server_menu)
            self._clear_busy()
            self._reopen_followup_screen(reopen_after_action)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._busy:
            return
        item = event.item
        if not isinstance(item, ValueListItem):
            return
        list_id = event.list_view.id or ""
        if list_id == "sections-list":
            screen = normalize_screen(str(item.value))
            if screen == "configure_menu":
                self._open_configure_menu()
                return
            if screen == "server_menu":
                self._open_server_menu()
                return
            if screen == "language":
                self._open_language_menu()
                return
            if screen == self.state.current_screen:
                return
            self._open_screen(screen)
            await self.refresh_ui(refresh_sections=False)
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
            if screen in {"configure_menu", "server_menu", "language"}:
                return
            if screen != self.state.current_screen:
                self._open_screen(screen)
                await self.refresh_ui(refresh_sections=False)
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

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if self._busy or event.data_table.id != "users-table" or self.state.current_screen != "users":
            return
        if not self._users_row_selected:
            return
        users = self._sorted_users_snapshot()
        if 0 <= event.cursor_row < len(users):
            user_name = users[event.cursor_row].name
            if user_name != self.state.selected_user:
                self.state.selected_user = user_name

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._busy or event.data_table.id != "users-table" or self.state.current_screen != "users":
            return
        users = self._sorted_users_snapshot()
        if 0 <= event.cursor_row < len(users):
            user_name = users[event.cursor_row].name
            if user_name == self.state.selected_user and self._users_row_selected:
                self._users_row_selected = False
                self._set_users_table_selection_state(event.data_table)
                await self._refresh_action_bar()
                event.data_table.focus()
                return
            self.state.selected_user = user_name
            self._users_row_selected = True
            self._set_users_table_selection_state(event.data_table)
            await self._refresh_action_bar()
            return

    async def on_users_table_row_clicked(self, message: UsersTable.RowClicked) -> None:
        if self._busy or self.state.current_screen != "users":
            return
        users = self._sorted_users_snapshot()
        if not (0 <= message.row_index < len(users)):
            return
        table = message.table
        user_name = users[message.row_index].name
        if user_name == self.state.selected_user and self._users_row_selected:
            self._users_row_selected = False
            self._set_users_table_selection_state(table)
            await self._refresh_action_bar()
            table.focus()
            return
        self.state.selected_user = user_name
        self._users_row_selected = True
        self._set_users_table_selection_state(table)
        await self._refresh_action_bar()
        table.move_cursor(row=message.row_index, column=0, animate=False, scroll=True)
        table.focus()

    async def on_users_table_header_clicked(self, message: UsersTable.HeaderClicked) -> None:
        if self._busy or self.state.current_screen != "users":
            return
        column = message.column_key
        if column == self._users_sort_column:
            self._users_sort_reverse = not self._users_sort_reverse
        else:
            self._users_sort_column = column
            self._users_sort_reverse = False
        self._apply_users_table_sort(message.table)
        message.table.focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._busy:
            return
        button_id = event.button.id or ""
        if not button_id.startswith("action-"):
            return
        action = button_id.removeprefix("action-")
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
        if action == "server_menu":
            self._open_server_menu()
            return
        if action == "more":
            overflow = list(self._secondary_actions.values())
            if overflow:
                self.push_screen(
                    ActionMenuScreen(
                        self._t("actions"),
                        translated_actions(overflow, self._t),
                        close_label=self._t("close", "Close"),
                    ),
                    self._handle_action_menu,
                )
            return
        if action == "edit_settings":
            self.push_screen(
                SettingsScreen(
                    self.controller.load_settings(),
                    title=self._t("edit_settings"),
                    save_label=self._t("save", "Save"),
                    cancel_label=self._t("cancel", "Cancel"),
                    mt_port_label=self._t("proxy_port"),
                    stats_port_label=self._t("api_port"),
                    workers_label=self._t("workers"),
                    fake_tls_domain_label=self._t("fake_tls_domain"),
                    ad_tag_label=self._t("ad_tag"),
                ),
                self._handle_settings_screen,
            )
            return
        if action == "user_configure":
            self._open_user_configure_menu()
            return
        if action == "user_secrets":
            self._open_user_secrets_screen()
            return
        if action == "show_export":
            self._run_action(
                lambda: self.controller.export_text_for_user(self.state.selected_user),
                output_title=self._t("export_title"),
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
                busy_label=f"{self._t('update_source', 'Sync')}...",
            )
            return
        if action == "rebuild":
            self._run_action(
                self.controller.run_rebuild,
                busy_label=f"{self._t('rebuild', 'Reinstall')}...",
            )
            return
        if action == "install_ref":
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
            return
        if action == "add_user":
            self.push_screen(
                TextInputScreen(
                    self._t("add_user"),
                    self._t("add_user_prompt"),
                    save_label=self._t("save", "Save"),
                    cancel_label=self._t("cancel", "Cancel"),
                    submit_handler=self._can_submit_add_user,
                ),
                self._handle_add_user,
            )
            return
        if action == "add_secret":
            user_name = self._selected_user_for_actions()
            if not user_name:
                self._notify_result(self._t("select_user_to_continue"), severity="warning")
                return
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
        if action == "enable_user":
            user_name = self._selected_user_for_actions()
            if not user_name:
                self._notify_result(self._t("select_user_to_continue"), severity="warning")
                return
            self._run_action(lambda: self.controller.set_user_enabled(user_name, True))
            return
        if action == "disable_user":
            user_name = self._selected_user_for_actions()
            if not user_name:
                self._notify_result(self._t("select_user_to_continue"), severity="warning")
                return
            self._run_action(lambda: self.controller.set_user_enabled(user_name, False))
            return
        if action == "rotate_user":
            user_name = self._selected_user_for_actions()
            if not user_name:
                self._notify_result(self._t("select_user_to_continue"), severity="warning")
                return
            self._run_action(lambda: self.controller.rotate_user(user_name))
            return
        if action == "delete_user":
            user_name = self._selected_user_for_actions()
            if not user_name:
                self._notify_result(self._t("select_user_to_continue"), severity="warning")
                return
            self.push_screen(
                ConfirmScreen(
                    self._t("delete_user_title"),
                    self._delete_user_confirm_text(user_name),
                    self._t("delete", "Delete"),
                    cancel_label=self._t("cancel", "Cancel"),
                    confirm_variant="error",
                    center_message=True,
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
                self._notify_result(self._t("select_secret_to_continue"), severity="warning")
                return
            self.push_screen(
                ConfirmScreen(
                    self._t("delete_secret_title"),
                    self._delete_secret_confirm_text(self.state.selected_secret_id),
                    self._t("delete", "Delete"),
                    cancel_label=self._t("cancel", "Cancel"),
                    confirm_variant="error",
                    center_message=True,
                ),
                self._handle_delete_secret,
            )
            return
        if action == "export_to_file":
            self._run_action(
                lambda: self.controller.export_selected_user_to_file(self.state.selected_user),
                output_title=self._t("export_file_title"),
            )
            return
        if action == "server_start":
            self._run_action(self.controller.service_start)
            return
        if action == "server_stop":
            self._run_action(self.controller.service_stop)
            return
        if action == "server_restart":
            self._run_action(self.controller.service_restart)
            return
        if action == "server_status":
            self.state.output_title = self._t("activity")
            self.state.output_body = ""
            self.run_worker(self.refresh_ui(), exclusive=True)
            self._open_server_status_screen()
            return
        if action == "server_logs":
            self.state.output_title = self._t("activity")
            self.state.output_body = ""
            self.run_worker(self.refresh_ui(), exclusive=True)
            self._open_server_logs_screen()
            return
        if action == "cleanup":
            self._reopen_screen_after_action = "configure_menu"
            self._run_action(
                self._run_cleanup,
                busy_label=f"{self._t('cleanup', 'Cleanup')}...",
            )
            return
        if action == "factory_reset":
            self.push_screen(
                ConfirmScreen(
                    self._t("factory_reset"),
                    self._t("factory_reset_confirm"),
                    self._t("factory_reset"),
                    cancel_label=self._t("cancel", "Cancel"),
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
            return
        if action == "lang_zh":
            self._change_language("zh")

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
        current_screen = self.screen
        if isinstance(current_screen, ConfirmScreen) and current_screen.title_text == self._t("quit_confirm_title", "Quit"):
            return
        self._open_quit_confirmation()

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
