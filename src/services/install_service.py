from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from errors import PlatformError
from infra.distro import DistroProbe
from infra.locale import LocaleManager
from infra.shell import ShellRunner
from infra.ufw import UfwManager
from models.settings import AppSettings
from services.proxy_runtime_service import ProxyRuntimeService
from services.source_service import SourceService
from services.systemd_service import SystemdService


@dataclass(frozen=True, slots=True)
class SetupOptions:
    source_mode: str = "fresh"
    install_dependencies: bool = True
    configure_firewall: bool = True


class InstallService:
    def __init__(
        self,
        shell: ShellRunner,
        distro: DistroProbe,
        locale: LocaleManager,
        source: SourceService,
        runtime: ProxyRuntimeService,
        systemd: SystemdService,
        ufw: UfwManager,
    ) -> None:
        self.shell = shell
        self.distro = distro
        self.locale = locale
        self.source = source
        self.runtime = runtime
        self.systemd = systemd
        self.ufw = ufw

    def _stop_service_for_binary_update(self) -> None:
        if self.systemd.is_installed():
            self.systemd.stop()

    def initial_setup(self, settings: AppSettings, script_path: Path, options: SetupOptions) -> None:
        if os.geteuid() != 0:
            raise PlatformError("this action requires root")
        self.distro.detect()
        self.locale.ensure_c_utf8()
        if options.install_dependencies:
            self.shell.run(["apt-get", "update"])
            self.shell.run(["apt-get", "install", "-y", "curl", "ca-certificates", "ufw"])
        self._stop_service_for_binary_update()
        self.source.install(options.source_mode)
        self.systemd.write_units(script_path)
        enabled_count = self.runtime.reconcile(settings, self.systemd, restart=False)
        if options.configure_firewall:
            self.ufw.allow_tcp(22)
            self.ufw.allow_tcp(settings.mt_port)
        if enabled_count > 0:
            self.systemd.start()

    def update_source(self, settings: AppSettings, script_path: Path, *, source_mode: str = "update") -> None:
        self.initial_setup(settings, script_path, SetupOptions(source_mode=source_mode, install_dependencies=False, configure_firewall=True))

    def rebuild_source(self, settings: AppSettings) -> None:
        self._stop_service_for_binary_update()
        self.source.install("rebuild")
        self.runtime.reconcile(settings, self.systemd, restart=True)

    def reinstall_units(self, script_path: Path) -> None:
        self.systemd.write_units(script_path)

    def refresh_proxy_config(self, settings: AppSettings) -> bool:
        previous = self.runtime.paths.telemt_config_file.read_text(encoding="utf-8") if self.runtime.paths.telemt_config_file.exists() else ""
        self.runtime.reconcile(settings, self.systemd, restart=True)
        current = self.runtime.paths.telemt_config_file.read_text(encoding="utf-8") if self.runtime.paths.telemt_config_file.exists() else ""
        return current != previous

    def refresh_runtime(self, settings: AppSettings) -> int:
        return self.runtime.reconcile(settings, self.systemd, restart=True)
