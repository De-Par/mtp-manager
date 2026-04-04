from __future__ import annotations

import textwrap
from pathlib import Path

from infra.storage import JsonStorage
from infra.systemd import SystemdManager
from paths import ProjectPaths


class SystemdService:
    MAIN_UNIT = "telemt.service"

    def __init__(self, systemd: SystemdManager, storage: JsonStorage, paths: ProjectPaths) -> None:
        self.systemd = systemd
        self.storage = storage
        self.paths = paths

    def render_main_unit(self, script_path: Path) -> str:
        return textwrap.dedent(
            f"""\
            [Unit]
            Description=telemt proxy managed by mtp-manager
            After=network-online.target
            Wants=network-online.target

            [Service]
            Type=simple
            WorkingDirectory={self.paths.mt_dir}
            ExecStart={script_path} internal run-proxy
            Restart=on-failure
            RestartSec=2
            NoNewPrivileges=true
            LimitNOFILE=65535
            OOMScoreAdjust=-250

            [Install]
            WantedBy=multi-user.target
            """
        )

    def render_refresh_service(self, script_path: Path) -> str:
        return textwrap.dedent(
            f"""\
            [Unit]
            Description=Refresh managed telemt config

            [Service]
            Type=oneshot
            ExecStart={script_path} internal refresh-proxy-config
            """
        )

    def render_refresh_timer(self) -> str:
        return textwrap.dedent(
            """\
            [Unit]
            Description=Daily telemt config refresh

            [Timer]
            OnBootSec=10m
            OnUnitActiveSec=1d
            Persistent=true

            [Install]
            WantedBy=timers.target
            """
        )

    def render_cleanup_service(self, script_path: Path) -> str:
        return textwrap.dedent(
            f"""\
            [Unit]
            Description=Daily cleanup for mtp-manager artifacts

            [Service]
            Type=oneshot
            ExecStart={script_path} internal run-cleanup
            """
        )

    def render_cleanup_timer(self) -> str:
        return textwrap.dedent(
            """\
            [Unit]
            Description=Daily cleanup timer for mtp-manager

            [Timer]
            OnBootSec=15m
            OnUnitActiveSec=1d
            Persistent=true

            [Install]
            WantedBy=timers.target
            """
        )

    def write_units(self, script_path: Path, *, enable_timers: bool = True) -> None:
        self._remove_legacy_units()
        self.storage.save_text(self.paths.service_file, self.render_main_unit(script_path))
        self.storage.save_text(self.paths.refresh_service_file, self.render_refresh_service(script_path))
        self.storage.save_text(self.paths.refresh_timer_file, self.render_refresh_timer())
        self.storage.save_text(self.paths.cleanup_service_file, self.render_cleanup_service(script_path))
        self.storage.save_text(self.paths.cleanup_timer_file, self.render_cleanup_timer())
        self.systemd.daemon_reload()
        if enable_timers:
            self.systemd.enable(self.paths.refresh_timer_file.name)
            self.systemd.enable(self.paths.cleanup_timer_file.name)

    def is_installed(self) -> bool:
        return self.paths.service_file.exists() or self.paths.legacy_service_file.exists()

    def start(self) -> None:
        self.systemd.start(self._preferred_main_unit())

    def stop(self) -> None:
        self.systemd.stop(self._preferred_main_unit())

    def restart(self) -> None:
        self.systemd.restart(self._preferred_main_unit())

    def try_restart(self) -> None:
        self.systemd.try_restart(self._preferred_main_unit())

    def state(self) -> str:
        if not self.is_installed():
            return "not-installed"
        return self.systemd.is_active(self._preferred_main_unit())

    def status(self) -> str:
        return self.systemd.status(self._preferred_main_unit())

    def logs(self) -> str:
        since = None
        if self.paths.service_logs_marker_file.exists():
            raw_since = self.paths.service_logs_marker_file.read_text(encoding="utf-8").strip()
            since = raw_since or None
        return self.systemd.logs(self._preferred_main_unit(), since=since)

    def preview(self) -> str:
        return self.systemd.cat(self._preferred_main_unit())

    def disable_all(self) -> None:
        for unit in self.paths.all_unit_names:
            self.systemd.disable(unit)

    def _preferred_main_unit(self) -> str:
        if self.paths.service_file.exists():
            return self.paths.service_file.name
        if self.paths.legacy_service_file.exists():
            return self.paths.legacy_service_file.name
        return self.MAIN_UNIT

    def _remove_legacy_units(self) -> None:
        for unit in self.paths.legacy_unit_names:
            self.systemd.disable(unit)
        for unit_file in self.paths.legacy_unit_files:
            unit_file.unlink(missing_ok=True)
