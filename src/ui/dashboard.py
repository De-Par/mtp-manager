"""Dashboard rendering and host resource snapshot helpers"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable

from rich.cells import cell_len
from rich.text import Text

from controller import DashboardViewModel

StatusTranslateFn = Callable[[str], str]
BASE_TEXT_STYLE = "#1f2937"
TITLE_TEXT_STYLE = "bold #275a45"


def render_fields(body: str) -> Text:
    """Render simple field-style text blocks used outside the dashboard card"""
    text = Text()
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line:
            text.append("\n")
            continue
        if ": " in line:
            label, value = line.split(": ", 1)
            text.append(f"{label}: ", style=BASE_TEXT_STYLE)
            text.append(value, style=BASE_TEXT_STYLE)
        elif line.startswith("- "):
            text.append(line, style=BASE_TEXT_STYLE)
        else:
            text.append(line, style=TITLE_TEXT_STYLE)
        text.append("\n")
    return text


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit in {"B", "KB"}:
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def _usage_percent_style(percent: float) -> str:
    if percent >= 90:
        return "bold #e03131"
    if percent >= 75:
        return "bold #f76707"
    if percent >= 50:
        return "bold #ffd43b"
    return "bold #37b24d"


def _usage_metric_text(used: int, total: int) -> Text:
    percent = (used / total * 100) if total > 0 else 0.0
    text = Text()
    text.append(f"{_format_bytes(used)} / {_format_bytes(total)} ", style=BASE_TEXT_STYLE)
    text.append(f"{percent:.0f}%", style=_usage_percent_style(percent))
    return text


def _meminfo_values() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for raw_line in handle:
                if ":" not in raw_line:
                    continue
                key, raw_value = raw_line.split(":", 1)
                parts = raw_value.strip().split()
                if not parts:
                    continue
                amount = int(parts[0])
                unit = parts[1].lower() if len(parts) > 1 else ""
                values[key] = amount * 1024 if unit == "kb" else amount
    except OSError:
        return {}
    return values


def capture_hardware_snapshot() -> list[tuple[str, object]]:
    """Collect lightweight RAM, swap, disk, and CPU metrics for the dashboard"""
    snapshot: list[tuple[str, object]] = []
    meminfo = _meminfo_values()
    ram_total = meminfo.get("MemTotal", 0)
    ram_free = meminfo.get("MemAvailable", 0)
    if ram_total:
        ram_used = max(0, ram_total - ram_free)
        snapshot.extend(
            [
                ("", ""),
                ("ram", _usage_metric_text(ram_used, ram_total)),
            ]
        )
        swap_total = meminfo.get("SwapTotal", 0)
        swap_free = meminfo.get("SwapFree", 0)
        if swap_total > 0:
            swap_used = max(0, swap_total - swap_free)
            snapshot.append(("swap", _usage_metric_text(swap_used, swap_total)))
    try:
        disk = shutil.disk_usage("/")
    except OSError:
        disk = None
    if disk is not None:
        if not snapshot:
            snapshot.append(("", ""))
        snapshot.append(("disk", _usage_metric_text(disk.used, disk.total)))
    cpu_count = os.cpu_count()
    if cpu_count:
        if not snapshot:
            snapshot.append(("", ""))
        snapshot.append(("cpu_cores", str(cpu_count)))
    return snapshot


def build_status_metrics(
    dashboard: DashboardViewModel,
    hardware_snapshot: list[tuple[str, object]],
    translate: StatusTranslateFn,
) -> list[tuple[str, object]]:
    """Build localized status rows for the dashboard card"""
    service_status = translate(dashboard.service_status.lower().replace("-", "_").replace(" ", "_"))
    if service_status == dashboard.service_status.lower().replace("-", "_").replace(" ", "_"):
        service_status = dashboard.service_status
    metrics = [
        (translate("service_status"), service_status),
        (translate("public_ip"), dashboard.public_ip),
        (translate("telemt_version"), dashboard.telemt_version),
        (translate("proxy_port"), str(dashboard.mt_port)),
        (translate("api_port"), str(dashboard.stats_port)),
        (translate("fake_tls"), dashboard.fake_tls_domain or translate("disabled")),
        (translate("users_count"), str(dashboard.users_count)),
        (translate("secrets_count"), str(dashboard.secrets_count)),
    ]
    localized_hardware = [
        (translate(label), value) if label else (label, value)
        for label, value in hardware_snapshot
    ]
    return [*metrics, *localized_hardware]


def _status_indicator(value: str, *, state: str | None = None) -> Text:
    normalized_state = (state or value).lower().replace("-", "_").replace(" ", "_")
    indicator = "🟢" if normalized_state == "active" else "🟡" if normalized_state in {"activating", "reloading"} else "🔴"
    text = Text()
    text.append(f"{indicator} ")
    text.append(value, style=BASE_TEXT_STYLE)
    return text


def render_status_card(
    dashboard: DashboardViewModel,
    hardware_snapshot: list[tuple[str, object]],
    translate: StatusTranslateFn,
) -> Text:
    """Render the rich status card shown on the dashboard screen"""
    metrics = build_status_metrics(dashboard, hardware_snapshot, translate)
    service_status_label = translate("service_status")
    label_width = max((cell_len(label) for label, _ in metrics if label), default=12) + 2
    text = Text()
    for label, value in metrics:
        if not label and not value:
            text.append("\n")
            continue
        line = Text()
        line.append(" ")
        line.append(label.ljust(label_width), style=BASE_TEXT_STYLE)
        line.append(" : ", style=BASE_TEXT_STYLE)
        if label == service_status_label and isinstance(value, str):
            value_renderable = _status_indicator(value, state=dashboard.service_status)
        elif isinstance(value, Text):
            value_renderable = value
        else:
            value_renderable = Text(str(value), style=BASE_TEXT_STYLE)
        line.append_text(value_renderable)
        line.append("\n")
        text.append_text(line)
    return text
