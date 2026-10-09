from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path

from errors import PlatformError, ServiceError, SourceBuildRequiredError
from infra.distro import DistroProbe
from infra.firewall import FirewallManager
from infra.locale import LocaleManager
from infra.packages import PackageManager
from infra.shell import ShellRunner
from models.settings import AppSettings
from services.proxy_runtime_service import ProxyRuntimeService
from services.source_service import SourceService
from services.systemd_service import SystemdService
from services.https_service import HttpsService


@dataclass(frozen=True, slots=True)
class SetupOptions:
    source_mode: str = "fresh"
    install_dependencies: bool = True
    configure_firewall: bool = True
    progress: Callable[[str], None] | None = None


class InstallService:
    def __init__(
        self,
        shell: ShellRunner,
        distro: DistroProbe,
        packages: PackageManager,
        locale: LocaleManager,
        source: SourceService,
        runtime: ProxyRuntimeService,
        systemd: SystemdService,
        firewall: FirewallManager,
        https: HttpsService | None = None,
    ) -> None:
        self.shell = shell
        self.distro = distro
        self.packages = packages
        self.locale = locale
        self.source = source
        self.runtime = runtime
        self.systemd = systemd
        self.firewall = firewall
        self.https = https

    def _stop_service_for_binary_update(self) -> None:
        if self.systemd.is_installed():
            self.systemd.stop()

    def _install_packages(self, packages: list[str]) -> None:
        self.packages.install(packages)

    def _install_source_with_fallback(self, mode: str, ref: str, *, require_web: bool = False) -> None:
        try:
            self.source.install(mode, ref, allow_build=False, require_web=require_web)
        except SourceBuildRequiredError:
            self._install_packages(list(self.packages.package_set.build))
            self.source.install(mode, ref, allow_build=True, require_web=require_web)

    def preflight(self, settings: AppSettings) -> None:
        settings.validate()
        if os.geteuid() != 0:
            raise PlatformError("this action requires root")
        self.distro.detect()
        self.runtime.web.validate_decoy(settings)
        if self.https:
            self.https.validate_dns(settings)

    def initial_setup(self, settings: AppSettings, script_path: Path, options: SetupOptions) -> None:
        def progress(key: str) -> None:
            if options.progress:
                options.progress(key)

        progress("setup_checking")
        self.preflight(settings)
        self.locale.ensure_c_utf8()
        packages: list[str] = []
        if options.install_dependencies:
            packages.extend(self.packages.package_set.runtime)
        progress("setup_dependencies")
        self._install_packages(sorted(set(packages)))
        was_active = self.systemd.state() == "active"
        web_was_active = bool(self.https and self.https.is_installed()
                              and self.https.systemd.is_active(self.https.paths.web_service_file.name) == "active")
        self._stop_service_for_binary_update()
        if self.https:
            self.https.stop()
        try:
            self.check_runtime_ports(settings)
            if self.https and settings.web_enabled and settings.web_frontend == "caddy":
                self.https.check_ports_available()
        except Exception:
            if was_active:
                self.systemd.start()
            if web_was_active and self.https:
                self.https.systemd.start(self.https.paths.web_service_file.name)
            raise
        progress("setup_telemt")
        self._install_source_with_fallback(options.source_mode, settings.telemt_ref, require_web=settings.web_enabled)
        if self.https and settings.web_enabled and settings.web_frontend == "caddy":
            progress("setup_caddy")
            self.https.install_binary()
        progress("setup_configuring")
        self.systemd.write_units(script_path)
        enabled_count = self.runtime.reconcile(settings, self.systemd, restart=False)
        if options.configure_firewall:
            self.firewall.allow_tcp(22)
            for port in sorted(settings.public_ports):
                self.firewall.allow_tcp(port)
        if enabled_count > 0:
            self.systemd.start()
            self.wait_runtime_ready(settings)
        if self.https:
            progress("setup_https")
            self.https.activate(settings, wait=enabled_count > 0)

    @staticmethod
    def check_runtime_ports(settings: AppSettings) -> None:
        listeners = [("127.0.0.1", settings.stats_port)]
        if settings.mtproto_enabled:
            listeners.append(("0.0.0.0", settings.mt_port))
        if settings.web_enabled:
            listeners.append(("127.0.0.1", settings.web_port))
        for host, port in listeners:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((host, port))
            except OSError as exc:
                raise ServiceError(f"setup_port_in_use:{port}") from exc

    def wait_runtime_ready(self, settings: AppSettings, *, timeout: float = 30) -> None:
        ports = [settings.stats_port]
        if settings.mtproto_enabled:
            ports.append(settings.mt_port)
        if settings.web_enabled:
            ports.append(settings.web_port)
        deadline = time.monotonic() + timeout
        while True:
            try:
                for port in ports:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        pass
                if self.systemd.state() == "active":
                    return
            except OSError:
                pass
            if self.systemd.state() == "failed" or time.monotonic() >= deadline:
                raise ServiceError("setup_runtime_failed")
            time.sleep(1)

    def update_source(self, settings: AppSettings, script_path: Path, *, source_mode: str = "update") -> None:
        self.initial_setup(settings, script_path, SetupOptions(source_mode=source_mode, install_dependencies=False, configure_firewall=True))

    def rebuild_source(self, settings: AppSettings) -> None:
        settings.validate()
        self._stop_service_for_binary_update()
        self._install_source_with_fallback("rebuild", settings.telemt_ref, require_web=settings.web_enabled)
        self.runtime.reconcile(settings, self.systemd, restart=True)
