"""Busy-state, toast, and action-execution helpers for the Textual UI."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from rich.cells import cell_len
from rich.text import Text
from textual.widgets import Button

from models.secret import SecretRecord, UserRecord
from models.settings import AppSettings
from ui.state import UIState
from ui.theme import SCROLLBAR_COLOR_HOVER, SLATE_MUTED
from ui.widgets import ActionTaskResult

BUSY_FRAMES = ("⏳", "⌛")


def render_busy_bar(progress: float, *, width: int = 18) -> Text:
    """Render a compact progress bar used by the busy overlay."""
    filled = max(0, min(width, int((progress / 100) * width)))
    text = Text()
    if filled:
        text.append("▅" * filled, style=SCROLLBAR_COLOR_HOVER)
    if filled < width:
        text.append("▁" * (width - filled), style=SLATE_MUTED)
    return text


def busy_dialog_width(*, label: str, frame_index: int, viewport_width: int) -> int:
    """Pick a dialog width wide enough for the busy label without early wrapping."""
    frame = BUSY_FRAMES[frame_index % len(BUSY_FRAMES)]
    label_width = cell_len(f"{frame} {label}")
    content_width = max(18, label_width)
    desired_width = max(32, content_width + 6)
    available_width = max(20, min(76, viewport_width - 4, max(20, int(viewport_width * 0.72))))
    return max(20, min(desired_width, available_width))


def set_actions_disabled(buttons: Iterable[Button], disabled: bool) -> None:
    """Enable or disable the current action buttons as a group."""
    for button in buttons:
        button.disabled = disabled


def notify_result(
    state: UIState,
    notifier: Callable[..., None],
    message: str,
    *,
    severity: str = "information",
) -> None:
    """Mirror a notification into UI state and emit the toast."""
    state.status_message = message
    notifier(message, severity=severity)


def execute_action(
    fn: Callable[[], object],
    *,
    translate: Callable[..., str],
    present_error: Callable[[str], str],
    output_title: str | None = None,
    success_message: str | None = None,
) -> ActionTaskResult:
    """Run a controller action and normalize it into a UI-friendly result payload."""
    try:
        result = fn()
    except Exception as exc:
        return ActionTaskResult(translate("activity"), "", present_error(str(exc)), "error")

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
        status_message = translate("action_completed")
    return ActionTaskResult(output_title or translate("activity"), output_body, status_message)
