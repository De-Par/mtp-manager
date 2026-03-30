from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    root: Path
    self_install_path: Path = Path("/usr/local/bin/mtproxy-manager.py")
    mt_dir: Path = Path("/opt/MTProxy")
    conf_dir: Path = Path("/etc/mtproxy-manager")
    data_dir: Path = Path("/var/lib/mtproxy-manager")
    lock_file: Path = Path("/var/lock/mtproxy-manager.lock")
    export_file: Path = Path("/root/mtproxy-links.txt")
    service_file: Path = Path("/etc/systemd/system/mtproxy.service")
    refresh_service_file: Path = Path("/etc/systemd/system/mtproxy-config-update.service")
    refresh_timer_file: Path = Path("/etc/systemd/system/mtproxy-config-update.timer")
    cleanup_service_file: Path = Path("/etc/systemd/system/mtproxy-cleanup.service")
    cleanup_timer_file: Path = Path("/etc/systemd/system/mtproxy-cleanup.timer")
    sysctl_file: Path = Path("/etc/sysctl.d/99-mtproxy-vps.conf")
    locale_file: Path = Path("/etc/default/locale")
    fstab_file: Path = Path("/etc/fstab")
    swap_file: Path = Path("/swapfile")

    @property
    def package_root(self) -> Path:
        return self.root / "src"

    @property
    def settings_file(self) -> Path:
        return self.conf_dir / "settings.json"

    @property
    def inventory_file(self) -> Path:
        return self.data_dir / "inventory.json"

    @property
    def runtime_file(self) -> Path:
        return self.data_dir / "runtime.json"

    @property
    def secrets_file(self) -> Path:
        return self.conf_dir / "secrets.txt"

    @property
    def bin_dir(self) -> Path:
        return self.mt_dir / "objs" / "bin"

    @property
    def binary_file(self) -> Path:
        return self.bin_dir / "mtproto-proxy"

    @property
    def proxy_secret_file(self) -> Path:
        return self.bin_dir / "proxy-secret"

    @property
    def proxy_config_file(self) -> Path:
        return self.bin_dir / "proxy-multi.conf"

    @property
    def managed_swap_marker(self) -> Path:
        return self.data_dir / "managed_swap_1g"


def default_paths(root: Path | None = None) -> ProjectPaths:
    project_root = (root or Path.cwd()).resolve()
    state_root_raw = os.environ.get("MTPROXY_MANAGER_STATE_ROOT", "").strip()
    if not state_root_raw:
        return ProjectPaths(root=project_root)

    state_root = Path(state_root_raw).resolve()
    return ProjectPaths(
        root=project_root,
        self_install_path=state_root / "bin" / "mtproxy-manager.py",
        mt_dir=state_root / "opt" / "MTProxy",
        conf_dir=state_root / "etc" / "mtproxy-manager",
        data_dir=state_root / "var" / "lib" / "mtproxy-manager",
        lock_file=state_root / "var" / "lock" / "mtproxy-manager.lock",
        export_file=state_root / "exports" / "mtproxy-links.txt",
        service_file=state_root / "systemd" / "mtproxy.service",
        refresh_service_file=state_root / "systemd" / "mtproxy-config-update.service",
        refresh_timer_file=state_root / "systemd" / "mtproxy-config-update.timer",
        cleanup_service_file=state_root / "systemd" / "mtproxy-cleanup.service",
        cleanup_timer_file=state_root / "systemd" / "mtproxy-cleanup.timer",
        sysctl_file=state_root / "sysctl" / "99-mtproxy-vps.conf",
        locale_file=state_root / "etc" / "default" / "locale",
        fstab_file=state_root / "etc" / "fstab",
        swap_file=state_root / "swapfile",
    )
