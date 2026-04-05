from __future__ import annotations

import shutil
from pathlib import Path
import time

from infra.packages import PackageManager
from infra.storage import JsonStorage
from infra.systemd import SystemdManager
from paths import ProjectPaths


class CleanupService:
    def __init__(self, systemd: SystemdManager, storage: JsonStorage, paths: ProjectPaths, packages: PackageManager) -> None:
        self.systemd = systemd
        self.storage = storage
        self.paths = paths
        self.packages = packages

    def cleanup_runtime(self) -> None:
        for target in (self.paths.export_file, self.paths.runtime_file):
            if target.exists():
                target.unlink()

    def cleanup_logs(self) -> None:
        self.systemd.shell.run(["journalctl", "--rotate"], check=False)
        self.systemd.shell.run(["journalctl", "--vacuum-time=1d", "--vacuum-size=25M"], check=False)
        self.packages.cleanup()
        self.systemd.shell.run(["systemd-tmpfiles", "--clean"], check=False)
        self.systemd.shell.run(
            [
                "sh",
                "-lc",
                "find /var/log -type f \\( -name '*.gz' -o -name '*.old' -o -name '*.1' -o -name '*.journal~' \\) -delete",
            ],
            check=False,
        )
        self.systemd.shell.run(
            ["sh", "-lc", "find /tmp /var/tmp -xdev -mindepth 1 -mtime +1 -delete"],
            check=False,
        )
        self.systemd.shell.run(
            ["sh", "-lc", "rm -rf /var/crash/* /var/lib/apt/lists/* /var/cache/dnf/* /var/cache/pacman/pkg/* /root/.cache/* /var/cache/man/*"],
            check=False,
        )
        self.systemd.shell.run(["sh", "-lc", "sync && echo 3 > /proc/sys/vm/drop_caches"], check=False)

    def clear_service_logs(self) -> None:
        self.storage.save_text(self.paths.service_logs_marker_file, f"@{int(time.time()) + 2}\n")
        self.systemd.shell.run(["journalctl", "--rotate"], check=False)
        self.systemd.shell.run(["journalctl", "--vacuum-time=1s", "--vacuum-size=1M"], check=False)
        self.systemd.shell.run(
            [
                "sh",
                "-lc",
                "find /var/log/journal /run/log/journal -type f \\( -name '*.journal' -o -name '*.journal~' \\) -delete 2>/dev/null || true",
            ],
            check=False,
        )
        self.systemd.shell.run(["systemctl", "restart", "systemd-journald"], check=False)

    def refresh_runtime_snapshot(self) -> None:
        self.storage.save_json(self.paths.runtime_file, {"schema_version": 1, "status": "clean"})

    def factory_reset(self, *, remove_swap: bool = False) -> None:
        managed_swap_present = self.paths.managed_swap_marker.exists()
        for unit in self.paths.all_unit_names:
            self.systemd.disable(unit)
        for target in (
            self.paths.lock_file,
            self.paths.legacy_lock_file,
            self.paths.service_file,
            self.paths.refresh_service_file,
            self.paths.refresh_timer_file,
            self.paths.cleanup_service_file,
            self.paths.cleanup_timer_file,
            self.paths.legacy_service_file,
            self.paths.legacy_refresh_service_file,
            self.paths.legacy_refresh_timer_file,
            self.paths.legacy_cleanup_service_file,
            self.paths.legacy_cleanup_timer_file,
            self.paths.settings_file,
            self.paths.inventory_file,
            self.paths.runtime_file,
            self.paths.telemt_config_file,
            self.paths.secrets_file,
            self.paths.export_file,
            self.paths.sysctl_file,
            self.paths.legacy_export_file,
            self.paths.legacy_sysctl_file,
        ):
            if target.exists():
                target.unlink()
        for directory in (
            self.paths.conf_dir,
            self.paths.data_dir,
            self.paths.legacy_conf_dir,
            self.paths.legacy_data_dir,
        ):
            if directory.exists():
                shutil.rmtree(directory)
        if self.paths.mt_dir.exists():
            shutil.rmtree(self.paths.mt_dir)
        if self.paths.legacy_mt_dir.exists():
            shutil.rmtree(self.paths.legacy_mt_dir)
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
