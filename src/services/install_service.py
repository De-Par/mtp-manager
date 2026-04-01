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
from services.network_service import NetworkService, PROXY_CONFIG_URL, PROXY_SECRET_URL
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
        network: NetworkService,
        runtime: ProxyRuntimeService,
        systemd: SystemdService,
        ufw: UfwManager,
    ) -> None:
        self.shell = shell
        self.distro = distro
        self.locale = locale
        self.source = source
        self.network = network
        self.runtime = runtime
        self.systemd = systemd
        self.ufw = ufw

    def ensure_proxy_assets(self) -> None:
        self.network.download(PROXY_SECRET_URL, self.runtime.paths.proxy_secret_file)
        self.network.download(PROXY_CONFIG_URL, self.runtime.paths.proxy_config_file)

    def initial_setup(self, settings: AppSettings, script_path: Path, options: SetupOptions) -> None:
        if os.geteuid() != 0:
            raise PlatformError("this action requires root")
        self.distro.detect()
        self.locale.ensure_c_utf8()
        if options.install_dependencies:
            self.shell.run(["apt-get", "update"])
            self.shell.run(["apt-get", "install", "-y", "curl", "git", "build-essential", "libssl-dev", "zlib1g-dev", "ca-certificates", "ufw"])
        self.source.clone_or_update(options.source_mode)
        self.source.build()
        self.ensure_proxy_assets()
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
        self.source.clone_or_update("rebuild")
        self.source.build()
        self.ensure_proxy_assets()
        self.runtime.reconcile(settings, self.systemd, restart=True)

    def reinstall_units(self, script_path: Path) -> None:
        self.systemd.write_units(script_path)

    def refresh_proxy_config(self) -> bool:
        changed = self.network.refresh_if_changed(PROXY_CONFIG_URL, self.runtime.paths.proxy_config_file)
        if changed and self.systemd.is_installed():
            self.systemd.try_restart()
        return changed

    def refresh_runtime(self, settings: AppSettings) -> int:
        self.ensure_proxy_assets()
        return self.runtime.reconcile(settings, self.systemd, restart=True)
