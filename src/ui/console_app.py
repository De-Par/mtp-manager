from __future__ import annotations

from controller import AppController
from ui.backend import UIBackend
from ui.screens import dashboard_screen


class ConsoleApp(UIBackend):
    def run(self, controller: AppController) -> int:
        print(dashboard_screen(controller))
        return 0
