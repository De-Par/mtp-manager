from __future__ import annotations

import socket
import urllib.request


class PublicIpResolver:
    def __init__(self, url: str = "https://api.ipify.org") -> None:
        self.url = url

    def detect(self) -> str:
        try:
            with urllib.request.urlopen(self.url, timeout=8) as response:
                return response.read().decode("utf-8").strip()
        except Exception:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0].strip()
        except Exception:
            return ""
