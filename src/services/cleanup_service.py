from __future__ import annotations

import shutil
from pathlib import Path

from infra.storage import JsonStorage
from infra.systemd import SystemdManager
from paths import ProjectPaths


class CleanupService:
    def __init__(self, systemd: SystemdManager, storage: JsonStorage, paths: ProjectPaths) -> None:
        self.systemd = systemd
        self.storage = storage
        self.paths = paths

    def cleanup_runtime(self) -> None:
        for target in (self.paths.export_file, self.paths.runtime_file):
            if target.exists():
                target.unlink()

    def cleanup_logs(self) -> None:
        self.systemd.shell.run(["journalctl", "--vacuum-time=1d", "--vacuum-size=50M"], check=False)
        self.systemd.shell.run(["apt-get", "clean"], check=False)

    def refresh_runtime_snapshot(self) -> None:
        self.storage.save_json(self.paths.runtime_file, {"schema_version": 1, "status": "clean"})

    def factory_reset(self, *, remove_swap: bool = False) -> None:
        managed_swap_present = self.paths.managed_swap_marker.exists()
        for unit in ("mtproxy.service", self.paths.refresh_timer_file.name, self.paths.cleanup_timer_file.name):
            self.systemd.disable(unit)
        for target in (
            self.paths.lock_file,
            self.paths.service_file,
            self.paths.refresh_service_file,
            self.paths.refresh_timer_file,
            self.paths.cleanup_service_file,
            self.paths.cleanup_timer_file,
            self.paths.settings_file,
            self.paths.inventory_file,
            self.paths.runtime_file,
            self.paths.secrets_file,
            self.paths.export_file,
            self.paths.sysctl_file,
        ):
            if target.exists():
                target.unlink()
        for directory in (self.paths.conf_dir, self.paths.data_dir):
            if directory.exists():
                shutil.rmtree(directory)
        if self.paths.mt_dir.exists():
            shutil.rmtree(self.paths.mt_dir)
        install_path = self.paths.self_install_path
        if (
            install_path.exists()
            and install_path.name == "mtp-manager"
            and install_path.parent in {Path("/usr/local/bin"), Path("/usr/bin")}
        ):
            install_path.unlink()
        if remove_swap and managed_swap_present:
            self.systemd.shell.run(["swapoff", str(self.paths.swap_file)], check=False)
            if self.paths.fstab_file.exists():
                rows = [
                    line
                    for line in self.paths.fstab_file.read_text(encoding="utf-8").splitlines()
                    if "/swapfile none swap sw 0 0" not in line
                ]
                body = "\n".join(rows).rstrip()
                self.storage.save_text(self.paths.fstab_file, body + ("\n" if body else ""))
            if self.paths.swap_file.exists():
                self.paths.swap_file.unlink()
            self.paths.managed_swap_marker.unlink(missing_ok=True)
        self.systemd.daemon_reload()
