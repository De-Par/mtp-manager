"""Reusable widgets and support types for the main Textual app."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import sys

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.message import Message
from textual.widgets import DataTable, Label, ListItem, Static

from models.secret import UserRecord
from ui.theme import ACCENT_LIGHT_BG, APP_HEADER_FG

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
        super().__init__(Label(Text(label, no_wrap=True, overflow="ellipsis"), classes="list-label"))


class SplitHandle(Static):
    can_focus = True

    def __init__(self) -> None:
        super().__init__("│", id="top-split-handle")
        self._dragging = False

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.focus()
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


class TopbarClose(Container):
    can_focus = True

    def __init__(self) -> None:
        super().__init__(id="topbar-close")

    def compose(self) -> ComposeResult:
        yield Static("×", id="topbar-close-glyph")

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        self.focus()
        event.stop()

    async def _on_click(self, event: events.Click) -> None:
        event.stop()
        if hasattr(self.app, "_open_quit_confirmation"):
            self.app._open_quit_confirmation()

    async def _on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            event.stop()
            if hasattr(self.app, "_open_quit_confirmation"):
                self.app._open_quit_confirmation()


class UsersTable(DataTable):
    """Users table with stable custom mouse messages for rows and headers."""

    class HeaderClicked(Message):
        def __init__(self, table: "UsersTable", column_key: str) -> None:
            super().__init__()
            self.table = table
            self.column_key = column_key

    class RowClicked(Message):
        def __init__(self, table: "UsersTable", row_index: int) -> None:
            super().__init__()
            self.table = table
            self.row_index = row_index

    async def _on_click(self, event: events.Click) -> None:
        offset = event.get_content_offset_capture(self)
        y = max(0, int(offset.y))
        meta = event.style.meta
        row_index = meta.get("row")
        column_index = meta.get("column")

        if isinstance(row_index, int):
            if row_index == -1 and isinstance(column_index, int) and column_index >= 0:
                column = self.ordered_columns[column_index]
                self.post_message(self.HeaderClicked(self, column.key.value or str(column.key)))
                event.stop()
                return

        try:
            row_key, _ = self._get_offsets(int(self.scroll_y) + y)
        except LookupError:
            return
        if row_key == self._header_row_key:
            return
        row_index = self.get_row_index(row_key)

        self.post_message(self.RowClicked(self, row_index))
        event.stop()

    def _set_hover_cursor(self, active: bool) -> None:
        if self._show_hover_cursor:
            super()._set_hover_cursor(False)

    def _on_mouse_move(self, event: events.MouseMove) -> None:
        self._show_hover_cursor = False

    def _on_leave(self, event: events.Leave) -> None:
        self._show_hover_cursor = False

    def current_layout_signature(self, *, current_screen: str, users_subpanel: Vertical) -> tuple[int, int] | None:
        """Return the effective users-table geometry for resize-aware rerenders."""
        if current_screen != "users" or not self.is_attached:
            return None
        width_candidates = [
            users_subpanel.content_region.width,
            self.content_region.width,
            users_subpanel.size.width,
            self.size.width,
        ]
        height_candidates = [
            users_subpanel.content_region.height,
            self.content_region.height,
            users_subpanel.size.height,
            self.size.height,
        ]
        width = next((value for value in width_candidates if value and value > 0), 0)
        height = next((value for value in height_candidates if value and value > 0), 0)
        if width <= 0:
            return None
        return (width, height)

    @staticmethod
    def sorted_users(
        users_snapshot: Sequence[UserRecord],
        *,
        sort_column: str,
        sort_reverse: bool,
    ) -> list[UserRecord]:
        """Return users sorted according to the current table state."""
        users = list(users_snapshot)
        match sort_column:
            case "name":
                users.sort(key=lambda user: user.name.lower(), reverse=sort_reverse)
            case "enabled":
                users.sort(key=lambda user: (user.enabled, user.name.lower()), reverse=sort_reverse)
            case "secrets":
                users.sort(key=lambda user: (len(user.secrets), user.name.lower()), reverse=sort_reverse)
            case _:
                if sort_reverse:
                    users.reverse()
        return users

    @staticmethod
    def header_text(
        translate: Callable[..., str],
        *,
        sort_column: str,
        sort_reverse: bool,
        label_key: str,
        fallback: str,
        column_key: str,
    ) -> Text:
        """Build a centered header label with a sort marker for the active column."""
        label = translate(label_key, fallback)
        is_active = sort_column == column_key
        direction = "▾" if sort_reverse else "▴"
        text = Text(
            label,
            style=APP_HEADER_FG,
            justify="center",
            no_wrap=True,
            overflow="ellipsis",
        )
        if is_active:
            text.append(f" {direction}", style=ACCENT_LIGHT_BG)
        return text

    @staticmethod
    def cell_text(value: object) -> str:
        """Extract plain text from a cell value for sorting and comparisons."""
        if isinstance(value, Text):
            return value.plain
        renderable = getattr(value, "renderable", None)
        if renderable is not None and renderable is not value:
            return UsersTable.cell_text(renderable)
        plain = getattr(value, "plain", None)
        if isinstance(plain, str):
            return plain
        return str(value)

    def set_selection_state(self, row_selected: bool) -> None:
        """Keep selection styling in sync with the table's toggle state."""
        if row_selected:
            self.show_cursor = True
            self.remove_class("no-selection")
        else:
            self.show_cursor = False
            self.add_class("no-selection")
        self.refresh()

    def apply_sort(
        self,
        *,
        sort_column: str,
        sort_reverse: bool,
        selected_user: str | None,
        row_selected: bool,
        translate: Callable[..., str],
    ) -> None:
        """Apply sorting in-place and keep header labels plus selection consistent."""
        if self.row_count == 0:
            return

        match sort_column:
            case "name":
                self.sort(
                    "name",
                    key=lambda value: self.cell_text(value).lower(),
                    reverse=sort_reverse,
                )
            case "enabled":
                self.sort(
                    "enabled",
                    "name",
                    key=lambda values: (
                        0 if self.cell_text(values[0]) == "✅" else 1,
                        self.cell_text(values[1]).lower(),
                    ),
                    reverse=sort_reverse,
                )
            case "secrets":
                self.sort(
                    "secrets",
                    "name",
                    key=lambda values: (
                        int(self.cell_text(values[0]) or 0),
                        self.cell_text(values[1]).lower(),
                    ),
                    reverse=sort_reverse,
                )

        for column in self.ordered_columns:
            column_key = column.key.value or str(column.key)
            if column_key == "name":
                column.label = self.header_text(
                    translate,
                    sort_column=sort_column,
                    sort_reverse=sort_reverse,
                    label_key="name",
                    fallback="Name",
                    column_key="name",
                )
            elif column_key == "enabled":
                column.label = self.header_text(
                    translate,
                    sort_column=sort_column,
                    sort_reverse=sort_reverse,
                    label_key="enabled_short",
                    fallback="Enabled",
                    column_key="enabled",
                )
            elif column_key == "secrets":
                column.label = self.header_text(
                    translate,
                    sort_column=sort_column,
                    sort_reverse=sort_reverse,
                    label_key="secrets_count_short",
                    fallback="Secrets",
                    column_key="secrets",
                )

        if self.row_count == 0:
            return
        if selected_user and row_selected:
            try:
                selected_index = self.get_row_index(selected_user)
            except Exception:
                selected_index = 0
            self.move_cursor(row=selected_index, column=0, animate=False, scroll=False)
        self.set_selection_state(row_selected)

    def sync_rows(
        self,
        *,
        users_snapshot: Sequence[UserRecord],
        selected_user: str | None,
        sort_column: str,
        sort_reverse: bool,
        row_selected: bool,
        translate: Callable[..., str],
        panel_width: int,
    ) -> str | None:
        """Rebuild the users table for the current viewport width and sort state."""
        users = self.sorted_users(
            users_snapshot,
            sort_column=sort_column,
            sort_reverse=sort_reverse,
        )
        compact = panel_width < 80
        self.header_height = 1
        self.cell_padding = 0
        usable_width = max(30, panel_width - 4)
        enabled_width = 10 if compact else 14
        secrets_width = 9 if compact else 12
        name_width = max(10, usable_width - enabled_width - secrets_width)

        def cell(value: str, *, justify: str = "center") -> Text:
            return Text(value, justify=justify, no_wrap=True, overflow="ellipsis")

        self.clear(columns=True)
        self.add_column(
            self.header_text(
                translate,
                sort_column=sort_column,
                sort_reverse=sort_reverse,
                label_key="name",
                fallback="Name",
                column_key="name",
            ),
            key="name",
            width=name_width,
        )
        self.add_column(
            self.header_text(
                translate,
                sort_column=sort_column,
                sort_reverse=sort_reverse,
                label_key="enabled_short",
                fallback="Enabled",
                column_key="enabled",
            ),
            key="enabled",
            width=enabled_width,
        )
        self.add_column(
            self.header_text(
                translate,
                sort_column=sort_column,
                sort_reverse=sort_reverse,
                label_key="secrets_count_short",
                fallback="Secrets",
                column_key="secrets",
            ),
            key="secrets",
            width=secrets_width,
        )

        for user in users:
            self.add_row(
                cell(user.name),
                cell("✅" if user.enabled else "❌"),
                cell(str(len(user.secrets))),
                key=user.name,
                height=1,
            )

        if not users:
            return None
        if selected_user not in [user.name for user in users]:
            selected_user = users[0].name
        selected_index = next((index for index, user in enumerate(users) if user.name == selected_user), 0)
        if row_selected:
            self.move_cursor(row=selected_index, column=0, animate=False, scroll=True)
        self.set_selection_state(row_selected)
        return selected_user
