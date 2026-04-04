from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    root: Path
    self_install_path: Path = Path("/usr/local/bin/mtp-manager")
    mt_dir: Path = Path("/opt/telemt")
    conf_dir: Path = Path("/etc/mtp-manager")
    data_dir: Path = Path("/var/lib/mtp-manager")
    lock_file: Path = Path("/var/lock/mtp-manager.lock")
    export_file: Path = Path("/root/telemt-links.txt")
    service_file: Path = Path("/etc/systemd/system/telemt.service")
    refresh_service_file: Path = Path("/etc/systemd/system/telemt-config-refresh.service")
    refresh_timer_file: Path = Path("/etc/systemd/system/telemt-config-refresh.timer")
    cleanup_service_file: Path = Path("/etc/systemd/system/mtp-manager-cleanup.service")
    cleanup_timer_file: Path = Path("/etc/systemd/system/mtp-manager-cleanup.timer")
    sysctl_file: Path = Path("/etc/sysctl.d/99-mtp-manager-vps.conf")
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
    def service_logs_marker_file(self) -> Path:
        return self.data_dir / "service_logs_since.txt"

    @property
    def secrets_file(self) -> Path:
        return self.conf_dir / "secrets.txt"

    @property
    def bin_dir(self) -> Path:
        return self.mt_dir / "bin"

    @property
    def binary_file(self) -> Path:
        return self.bin_dir / "telemt"

    @property
    def telemt_config_file(self) -> Path:
        return self.conf_dir / "telemt.toml"

    @property
    def tls_front_dir(self) -> Path:
        return self.mt_dir / "tlsfront"

    @property
    def managed_swap_marker(self) -> Path:
        return self.data_dir / "managed_swap_1g"

    @property
    def legacy_mt_dir(self) -> Path:
        return self.mt_dir.parent / "MTProxy"

    @property
    def legacy_conf_dir(self) -> Path:
        return self.conf_dir.parent / "mtproxy-manager"

    @property
    def legacy_data_dir(self) -> Path:
        return self.data_dir.parent / "mtproxy-manager"

    @property
    def legacy_lock_file(self) -> Path:
        return self.lock_file.with_name("mtproxy-manager.lock")

    @property
    def legacy_export_file(self) -> Path:
        return self.export_file.with_name("mtproxy-links.txt")

    @property
    def legacy_service_file(self) -> Path:
        return self.service_file.with_name("mtproxy.service")

    @property
    def legacy_refresh_service_file(self) -> Path:
        return self.refresh_service_file.with_name("mtproxy-config-update.service")

    @property
    def legacy_refresh_timer_file(self) -> Path:
        return self.refresh_timer_file.with_name("mtproxy-config-update.timer")

    @property
    def legacy_cleanup_service_file(self) -> Path:
        return self.cleanup_service_file.with_name("mtproxy-cleanup.service")

    @property
    def legacy_cleanup_timer_file(self) -> Path:
        return self.cleanup_timer_file.with_name("mtproxy-cleanup.timer")

    @property
    def legacy_sysctl_file(self) -> Path:
        return self.sysctl_file.with_name("99-mtproxy-vps.conf")

    @property
    def legacy_unit_files(self) -> tuple[Path, ...]:
        return (
            self.legacy_service_file,
            self.legacy_refresh_service_file,
            self.legacy_refresh_timer_file,
            self.legacy_cleanup_service_file,
            self.legacy_cleanup_timer_file,
        )

    @property
    def unit_names(self) -> tuple[str, ...]:
        return (
            self.service_file.name,
            self.refresh_service_file.name,
            self.refresh_timer_file.name,
            self.cleanup_service_file.name,
            self.cleanup_timer_file.name,
        )

    @property
    def legacy_unit_names(self) -> tuple[str, ...]:
        return tuple(path.name for path in self.legacy_unit_files)

    @property
    def all_unit_names(self) -> tuple[str, ...]:
        return (*self.unit_names, *self.legacy_unit_names)


def default_paths(root: Path | None = None) -> ProjectPaths:
    project_root = (root or Path.cwd()).resolve()
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and not argv0.startswith("-"):
        resolved_entrypoint = Path(argv0).resolve()
    else:
        resolved_entrypoint = None
    if resolved_entrypoint is None or not resolved_entrypoint.exists():
        venv_entrypoint = Path(sys.prefix).resolve() / "bin" / "mtp-manager"
        if venv_entrypoint.exists():
            resolved_entrypoint = venv_entrypoint
        else:
            resolved_entrypoint = None
    if resolved_entrypoint is None or not resolved_entrypoint.exists():
        which_entrypoint = shutil.which("mtp-manager")
        resolved_entrypoint = Path(which_entrypoint).resolve() if which_entrypoint else Path("/usr/local/bin/mtp-manager")
    self_install_path = resolved_entrypoint
    state_root_raw = os.environ.get("MTP_MANAGER_STATE_ROOT", "").strip() or os.environ.get("MTPROXY_MANAGER_STATE_ROOT", "").strip()
    if not state_root_raw:
        return ProjectPaths(root=project_root, self_install_path=self_install_path)

    state_root = Path(state_root_raw).resolve()
    return ProjectPaths(
        root=project_root,
        self_install_path=self_install_path,
        mt_dir=state_root / "opt" / "telemt",
        conf_dir=state_root / "etc" / "mtp-manager",
        data_dir=state_root / "var" / "lib" / "mtp-manager",
        lock_file=state_root / "var" / "lock" / "mtp-manager.lock",
        export_file=state_root / "exports" / "telemt-links.txt",
        service_file=state_root / "systemd" / "telemt.service",
        refresh_service_file=state_root / "systemd" / "telemt-config-refresh.service",
        refresh_timer_file=state_root / "systemd" / "telemt-config-refresh.timer",
        cleanup_service_file=state_root / "systemd" / "mtp-manager-cleanup.service",
        cleanup_timer_file=state_root / "systemd" / "mtp-manager-cleanup.timer",
        sysctl_file=state_root / "sysctl" / "99-mtp-manager-vps.conf",
        locale_file=state_root / "etc" / "default" / "locale",
        fstab_file=state_root / "etc" / "fstab",
        swap_file=state_root / "swapfile",
    )
