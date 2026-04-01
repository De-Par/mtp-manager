from __future__ import annotations

import socket
import urllib.request


class PublicIpResolver:
    def __init__(self, url: str = "https://api.ipify.org", timeout: float = 1.5) -> None:
        self.url = url
        self.timeout = timeout
        self._cached_ip = ""
        self._resolved = False

    def detect(self) -> str:
        if self._resolved:
            return self._cached_ip
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                detected = sock.getsockname()[0].strip()
                if detected:
                    self._cached_ip = detected
                    self._resolved = True
                    return detected
        except Exception:
            pass
        try:
            with urllib.request.urlopen(self.url, timeout=self.timeout) as response:
                detected = response.read().decode("utf-8").strip()
                if detected:
                    self._cached_ip = detected
                self._resolved = True
                return detected
        except Exception:
            self._resolved = True
        return ""
