from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class UIState:
    current_screen: str = "dashboard"
    status_message: str = ""
    selected_user: str | None = None
    selected_secret_id: int | None = None
    output_title: str = ""
    output_body: str = ""
