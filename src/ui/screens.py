from __future__ import annotations

from controller import AppController
from ui.panels import render_dashboard_panel, render_report_panel, render_settings_panel, render_users_panel


def dashboard_screen(controller: AppController) -> str:
    return render_dashboard_panel(controller.dashboard())


def setup_screen(controller: AppController) -> str:
    return render_settings_panel(controller.load_settings())


def users_screen(controller: AppController, selected_user: str | None, selected_secret_id: int | None) -> str:
    return render_users_panel(controller.list_users(), selected_user, selected_secret_id)


def service_screen(controller: AppController) -> str:
    return "\n".join(
        [
            f"State: {controller.dashboard().service_status}",
            "",
            "Unit preview:",
            controller.service_unit_preview(),
        ]
    )


def reports_screen(controller: AppController) -> str:
    return render_report_panel(controller.diagnostics())


def maintenance_screen(controller: AppController) -> str:
    return "\n".join(
        [
            "Maintenance actions available:",
            "- Cleanup runtime",
            "- Cleanup logs",
            "- Factory reset",
        ]
    )


def language_screen(controller: AppController) -> str:
    current = controller.load_settings().ui_lang
    return f"Current language: {current}\nChoose EN or RU via actions."
