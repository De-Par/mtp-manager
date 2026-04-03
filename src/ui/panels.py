from __future__ import annotations

from collections.abc import Callable

from controller import DashboardViewModel
from models.health import HealthReport
from models.settings import AppSettings


def render_dashboard_panel(model: DashboardViewModel, tr: Callable[[str], str] | None = None) -> str:
    translate = tr or (lambda key: key)
    fake_tls = model.fake_tls_domain or "disabled"
    return "\n".join(
        [
            f"🌿 {translate('dashboard')}",
            "",
            f"{translate('service')}: {model.service_status}",
            f"{translate('public_ip')}: {model.public_ip}",
            f"telemt version: {model.telemt_version}",
            f"Proxy port: {model.mt_port}",
            f"API port: {model.stats_port}",
            f"Workers (compat): {model.workers}",
            f"{translate('fake_tls')}: {fake_tls}",
            f"{translate('users_count')}: {model.users_count}",
            f"{translate('secrets_count')}: {model.secrets_count}",
        ]
    )


def render_settings_panel(settings: AppSettings, tr: Callable[[str], str] | None = None) -> str:
    translate = tr or (lambda key: key)
    return "\n".join(
        [
            f"⚙ {translate('settings')}",
            "",
            f"Proxy port: {settings.mt_port}",
            f"API port: {settings.stats_port}",
            f"Workers (compat): {settings.workers}",
            f"Fake TLS domain: {settings.fake_tls_domain or 'disabled'}",
            f"Ad tag: {settings.ad_tag or '-'}",
            f"{translate('language')}: {settings.ui_lang}",
            f"Managed swap: {'on' if settings.use_managed_swap else 'off'}",
            f"{translate('source_mode')}: {settings.source_mode}",
        ]
    )


def render_report_panel(report: HealthReport, tr: Callable[[str], str] | None = None) -> str:
    translate = tr or (lambda key: key)
    lines = [f"📈 {translate('diagnostics')}", ""]
    lines.extend(f"[{check.severity}] {check.label}: {check.value}" for check in report.checks)
    return "\n".join(lines)
