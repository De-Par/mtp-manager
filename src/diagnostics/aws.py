from __future__ import annotations

import urllib.request


def detect_aws_environment() -> bool:
    try:
        request = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/",
            headers={"Metadata": "true"},
        )
        with urllib.request.urlopen(request, timeout=0.2):
            return True
    except Exception:
        return False
