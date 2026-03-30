from __future__ import annotations

from prompt_toolkit.styles import Style


APP_STYLE = Style.from_dict(
    {
        "frame.label": "bold",
        "status": "bg:#1f2937 #f9fafb",
        "title": "bold #2563eb",
        "warning": "#b45309",
        "error": "#b91c1c",
        "ok": "#166534",
    }
)
