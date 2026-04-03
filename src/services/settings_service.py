from __future__ import annotations

from dataclasses import replace

from infra.storage import JsonStorage
from infra.ufw import UfwManager
from models.settings import AppSettings
from paths import ProjectPaths
from services.proxy_runtime_service import ProxyRuntimeService
from services.systemd_service import SystemdService


class SettingsService:
    def __init__(
        self,
        storage: JsonStorage,
        paths: ProjectPaths,
        runtime: ProxyRuntimeService | None = None,
        systemd: SystemdService | None = None,
        ufw: UfwManager | None = None,
    ) -> None:
        self.storage = storage
        self.paths = paths
        self.runtime = runtime
        self.systemd = systemd
        self.ufw = ufw

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
        self.save(updated)
        if self.ufw and updated.mt_port != current.mt_port:
            self.ufw.allow_tcp(22)
            self.ufw.allow_tcp(updated.mt_port)
            self.ufw.delete_allow_tcp(current.mt_port)
        if apply_runtime and self.runtime and self.systemd:
            self.runtime.reconcile(updated, self.systemd, restart=True)
        return updated
