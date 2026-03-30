from __future__ import annotations

from pathlib import Path
import urllib.request
import tempfile
import os

from infra.public_ip import PublicIpResolver

PROXY_SECRET_URL = "https://core.telegram.org/getProxySecret"
PROXY_CONFIG_URL = "https://core.telegram.org/getProxyConfig"


class NetworkService:
    def __init__(self, public_ip: PublicIpResolver) -> None:
        self.public_ip = public_ip

    def detect_public_ip(self) -> str:
        return self.public_ip.detect()

    def download(self, url: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read()
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(target.parent)) as handle:
            handle.write(body)
            tmp_path = Path(handle.name)
        os.replace(tmp_path, target)
        return target

    def refresh_if_changed(self, url: str, target: Path) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read()
        current = target.read_bytes() if target.exists() else b""
        if current == body:
            return False
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(target.parent)) as handle:
            handle.write(body)
            tmp_path = Path(handle.name)
        os.replace(tmp_path, target)
        return True
