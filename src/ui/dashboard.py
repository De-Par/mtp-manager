"""Dashboard rendering and host resource snapshot helpers"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable

from rich.cells import cell_len
from rich.text import Text

from controller import DashboardViewModel
from ui.theme import UI_ACCENT_INK, UI_INK, USAGE_CAUTION, USAGE_DANGER, USAGE_OK, USAGE_WARNING

StatusTranslateFn = Callable[[str], str]
BASE_TEXT_STYLE = UI_INK
TITLE_TEXT_STYLE = f"bold {UI_ACCENT_INK}"


def render_fields(body: str, *, align_fields: bool = False) -> Text:
    """Render simple field-style text blocks used outside the dashboard card"""
    label_width = 0
    if align_fields:
        label_width = max(
            (cell_len(raw_line.split(": ", 1)[0].rstrip()) for raw_line in body.splitlines() if ": " in raw_line),
            default=0,
        )
    text = Text()
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line:
            text.append("\n")
            continue
        if ": " in line:
            label, value = line.split(": ", 1)
            if align_fields and label_width > 0:
                text.append(_pad_to_cell_width(label, label_width), style=BASE_TEXT_STYLE)
                text.append(" : ", style=BASE_TEXT_STYLE)
            else:
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


def _byte_unit_index(value: int) -> int:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return unit_index


def _format_bytes_in_unit(value: int, unit_index: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    scaled = float(value) / (1024 ** unit_index)
    if units[unit_index] in {"B", "KB"}:
        return f"{int(scaled)}"
    return f"{scaled:.1f}"


def _pad_to_cell_width(value: str, width: int) -> str:
    """Pad text to a target display width, including wide CJK glyphs"""
    return value + (" " * max(0, width - cell_len(value)))


def _usage_percent_style(percent: float) -> str:
    if percent >= 90:
        return f"bold {USAGE_DANGER}"
    if percent >= 75:
        return f"bold {USAGE_WARNING}"
    if percent >= 50:
        return f"bold {USAGE_CAUTION}"
    return f"bold {USAGE_OK}"


def _usage_metric_text(used: int, total: int) -> Text:
    percent = (used / total * 100) if total > 0 else 0.0
    unit_index = _byte_unit_index(total) if total > 0 else 0
    units = ["B", "KB", "MB", "GB", "TB"]
    text = Text()
    text.append(
        f"{_format_bytes_in_unit(used, unit_index)} / {_format_bytes_in_unit(total, unit_index)} {units[unit_index]} ",
        style=BASE_TEXT_STYLE,
    )
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
        snapshot.append(("ram", _usage_metric_text(ram_used, ram_total)))
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
        snapshot.append(("disk", _usage_metric_text(disk.used, disk.total)))
    cpu_count = os.cpu_count()
    if cpu_count:
        snapshot.append(("cpu_cores", str(cpu_count)))
    return snapshot


def build_service_metrics(
    dashboard: DashboardViewModel,
    translate: StatusTranslateFn,
) -> list[tuple[str, object]]:
    """Build localized service rows for the dashboard card"""
    service_status = translate(dashboard.service_status.lower().replace("-", "_").replace(" ", "_"))
    if service_status == dashboard.service_status.lower().replace("-", "_").replace(" ", "_"):
        service_status = dashboard.service_status
    return [
        (translate("service_status"), service_status),
        (translate("public_ip"), dashboard.public_ip),
        (translate("telemt_version"), dashboard.telemt_version),
        (translate("proxy_port"), str(dashboard.mt_port)),
        (translate("api_port"), str(dashboard.stats_port)),
        (translate("fake_tls"), dashboard.fake_tls_domain or translate("disabled")),
        (translate("users_count"), str(dashboard.users_count)),
        (translate("secrets_count"), str(dashboard.secrets_count)),
    ]


def build_hardware_metrics(
    hardware_snapshot: list[tuple[str, object]],
    translate: StatusTranslateFn,
) -> list[tuple[str, object]]:
    """Build localized hardware rows for the dashboard card"""
    return [(translate(label), value) for label, value in hardware_snapshot]


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
    service_metrics = build_service_metrics(dashboard, translate)
    hardware_metrics = build_hardware_metrics(hardware_snapshot, translate)
    service_status_label = translate("service_status")
    text = Text(justify="center")
    _append_metric_lines(text, service_metrics, service_status_label=service_status_label, service_state=dashboard.service_status)
    if hardware_metrics:
        text.append("\n")
        _append_section_title(text, translate("hardware"), gap_after=1)
        _append_metric_lines(text, hardware_metrics, service_status_label=service_status_label, service_state=dashboard.service_status)
    return text


def _append_section_title(text: Text, title: str, *, gap_after: int = 0) -> None:
    text.append(title, style=TITLE_TEXT_STYLE)
    text.append("\n")
    if gap_after > 0:
        text.append("\n" * gap_after)


def _append_metric_lines(
    text: Text,
    metrics: list[tuple[str, object]],
    *,
    service_status_label: str,
    service_state: str,
) -> None:
    label_width = max((cell_len(label) for label, _ in metrics), default=0)
    rendered_values: list[tuple[str, Text]] = []
    section_width = 0

    for label, value in metrics:
        if label == service_status_label and isinstance(value, str):
            value_renderable = _status_indicator(value, state=service_state)
        elif isinstance(value, Text):
            value_renderable = value
        else:
            value_renderable = Text(str(value), style=BASE_TEXT_STYLE)
        rendered_values.append((label, value_renderable))
        section_width = max(section_width, label_width + 3 + cell_len(value_renderable.plain))

    for label, value_renderable in rendered_values:
        line = Text()
        line.append(_pad_to_cell_width(label, label_width), style=BASE_TEXT_STYLE)
        line.append(" : ", style=BASE_TEXT_STYLE)
        line.append_text(value_renderable)
        trailing_width = max(0, section_width - cell_len(line.plain))
        if trailing_width:
            line.append(" " * trailing_width, style=BASE_TEXT_STYLE)
        text.append_text(line)
        text.append("\n")
