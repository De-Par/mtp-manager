from __future__ import annotations

from typing import Protocol

from controller import AppController


class UIBackend(Protocol):
    def run(self, controller: AppController) -> int:
        ...
