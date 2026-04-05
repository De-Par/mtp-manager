from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from errors import PlatformError


@dataclass(frozen=True, slots=True)
class DistroInfo:
    distro_id: str
    version_id: str
    id_like: tuple[str, ...]
    family: str


class DistroProbe:
    SUPPORTED_FAMILIES = {"debian", "fedora", "arch"}

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
        distro_id = values.get("ID", "").strip().lower()
        id_like = tuple(part.strip().lower() for part in values.get("ID_LIKE", "").split() if part.strip())
        family = self._detect_family(distro_id, id_like)
        info = DistroInfo(distro_id, values.get("VERSION_ID", "unknown"), id_like, family)
        if info.family not in self.SUPPORTED_FAMILIES:
            raise PlatformError(f"unsupported distribution: {info.distro_id or 'unknown'}")
        return info

    @staticmethod
    def _detect_family(distro_id: str, id_like: tuple[str, ...]) -> str:
        candidates = (distro_id, *id_like)
        if any(name in {"debian", "ubuntu"} for name in candidates):
            return "debian"
        if any(name in {"fedora", "rhel", "centos", "rocky", "almalinux"} for name in candidates):
            return "fedora"
        if any(name in {"arch", "archlinux", "manjaro"} for name in candidates):
            return "arch"
        return distro_id
