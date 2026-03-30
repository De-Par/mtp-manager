from __future__ import annotations

from controller import DashboardViewModel
from models.health import HealthReport
from models.secret import UserRecord
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


def render_users_panel(users: list[UserRecord], selected_user: str | None, selected_secret_id: int | None) -> str:
    if not users:
        return "No users yet"
    lines: list[str] = []
    for user in users:
        marker = ">" if user.name == selected_user else " "
        enabled = "on" if user.enabled else "off"
        lines.append(f"{marker} {user.name} [{enabled}] secrets={len(user.secrets)}")
        for secret in user.secrets:
            secret_marker = "*" if user.name == selected_user and secret.id == selected_secret_id else "-"
            state = "on" if secret.enabled else "off"
            lines.append(f"    {secret_marker} #{secret.id} [{state}] {secret.raw_secret[:8]}... note={secret.note or '-'}")
    if selected_user:
        lines.append("")
        lines.append(f"Selected user: {selected_user}")
        lines.append(f"Selected secret: {selected_secret_id if selected_secret_id is not None else 'none'}")
    return "\n".join(lines)


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
