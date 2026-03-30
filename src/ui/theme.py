from __future__ import annotations

from prompt_toolkit.styles import Style


APP_STYLE = Style.from_dict(
    {
        "frame": "bg:#111827 #e5e7eb",
        "frame.border": "#334155",
        "frame.label": "bg:#0f172a #93c5fd bold",
        "header": "bg:#020617 #f8fafc bold",
        "status": "bg:#0f172a #cbd5e1",
        "button": "bg:#1f2937 #e5e7eb",
        "button.focused": "bg:#2563eb #eff6ff",
        "button.arrow": "bg:#1f2937 #60a5fa",
        "button.text": "bg:#1f2937 #e5e7eb bold",
        "section.title": "bold #93c5fd",
        "muted": "#94a3b8",
        "title": "bold #93c5fd",
        "warning": "#b45309",
        "error": "#b91c1c",
        "ok": "#166534",
    }
)
