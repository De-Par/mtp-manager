from __future__ import annotations


def summarize_service_status(raw_status: str) -> str:
    lines = [line.strip() for line in raw_status.splitlines() if line.strip()]
    return lines[0] if lines else "unknown"
