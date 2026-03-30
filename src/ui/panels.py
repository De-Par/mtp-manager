from __future__ import annotations

from controller import DashboardViewModel
from models.health import HealthReport
from models.settings import AppSettings


def render_dashboard_panel(model: DashboardViewModel) -> str:
    fake_tls = model.fake_tls_domain or "disabled"
    return "\n".join(
        [
            f"Service: {model.service_status}",
            f"Public IP: {model.public_ip}",
            f"Client port: {model.mt_port}",
            f"Stats port: {model.stats_port}",
            f"Workers: {model.workers}",
            f"Fake TLS: {fake_tls}",
            f"Users: {model.users_count}",
            f"Secrets: {model.secrets_count}",
        ]
    )
def render_settings_panel(settings: AppSettings) -> str:
    return "\n".join(
        [
            f"Client port: {settings.mt_port}",
            f"Stats port: {settings.stats_port}",
            f"Workers: {settings.workers}",
            f"Fake TLS domain: {settings.fake_tls_domain or 'disabled'}",
            f"Ad tag: {settings.ad_tag or '-'}",
            f"UI language: {settings.ui_lang}",
            f"Managed swap: {'on' if settings.use_managed_swap else 'off'}",
            f"Source mode: {settings.source_mode}",
        ]
    )


def render_report_panel(report: HealthReport) -> str:
    return "\n".join(f"[{check.severity}] {check.label}: {check.value}" for check in report.checks)
