from __future__ import annotations

from dataclasses import replace

from infra.firewall import FirewallManager
from infra.storage import JsonStorage
from models.settings import AppSettings
from paths import ProjectPaths
from services.proxy_runtime_service import ProxyRuntimeService
from services.systemd_service import SystemdService
from services.https_service import HttpsService


class SettingsService:
    def __init__(
        self,
        storage: JsonStorage,
        paths: ProjectPaths,
        runtime: ProxyRuntimeService | None = None,
        systemd: SystemdService | None = None,
        firewall: FirewallManager | None = None,
        https: HttpsService | None = None,
    ) -> None:
        self.storage = storage
        self.paths = paths
        self.runtime = runtime
        self.systemd = systemd
        self.firewall = firewall
        self.https = https

    def load(self) -> AppSettings:
        payload = self.storage.load_json(self.paths.settings_file, default={})
        if not payload:
            return AppSettings()
        return AppSettings.from_dict(payload)

    def save(self, settings: AppSettings) -> AppSettings:
        settings.validate()
        self.storage.save_json(self.paths.settings_file, settings.to_dict())
        return settings

    def update(self, *, apply_runtime: bool = True, **changes: object) -> AppSettings:
        current = self.load()
        updated = replace(current, **changes)
        updated.validate()
        if apply_runtime and self.runtime:
            self.runtime.validate_settings(updated)
        frontend_changed = any(getattr(updated, key) != getattr(current, key) for key in (
            "proxy_mode", "web_frontend", "web_domain", "web_public_ip", "web_port", "web_base_path",
        ))
        if apply_runtime and self.https and self.https.is_installed() and frontend_changed:
            self.https.validate_dns(updated)
            if not updated.web_enabled or updated.web_frontend != "caddy":
                self.https.deactivate()
        self.save(updated)
        if apply_runtime and self.firewall and updated.public_ports != current.public_ports:
            self.firewall.allow_tcp(22)
            for port in sorted(updated.public_ports - current.public_ports):
                self.firewall.allow_tcp(port)
            for port in sorted(current.public_ports - updated.public_ports - {22}):
                self.firewall.delete_allow_tcp(port)
        if apply_runtime and self.runtime and self.systemd:
            self.runtime.reconcile(updated, self.systemd, restart=True)
        if apply_runtime and self.https and self.https.is_installed() and frontend_changed:
            self.https.activate(updated)
        return updated
