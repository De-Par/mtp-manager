from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from errors import PlatformError


@dataclass(frozen=True, slots=True)
class DistroInfo:
    distro_id: str
    version_id: str


class DistroProbe:
    SUPPORTED = {"debian", "ubuntu"}

    def detect(self) -> DistroInfo:
        os_release = Path("/etc/os-release")
        if not os_release.exists():
            raise PlatformError("/etc/os-release is missing")
        values: dict[str, str] = {}
        for line in os_release.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
        info = DistroInfo(values.get("ID", ""), values.get("VERSION_ID", "unknown"))
        if info.distro_id not in self.SUPPORTED:
            raise PlatformError(f"unsupported distribution: {info.distro_id or 'unknown'}")
        return info
