from __future__ import annotations

import os

from errors import AppError, ServiceError
from infra.storage import JsonStorage
from models.secret import SecretRecord, UserRecord
from models.settings import AppSettings
from paths import ProjectPaths
from services.inventory_service import InventoryService
from services.systemd_service import SystemdService


class ProxyRuntimeService:
    def __init__(self, storage: JsonStorage, inventory: InventoryService, paths: ProjectPaths) -> None:
        self.storage = storage
        self.inventory = inventory
        self.paths = paths

    def rebuild_runtime_config(self, settings: AppSettings) -> str:
        if settings.fake_tls_domain:
            self.paths.tls_front_dir.mkdir(parents=True, exist_ok=True)
        body = self.render_config(settings)
        self.storage.save_text(self.paths.telemt_config_file, body)
        return body

    def _enabled_entries(self) -> list[tuple[str, UserRecord, SecretRecord]]:
        entries: list[tuple[str, UserRecord, SecretRecord]] = []
        for user in self.inventory.load_users():
            if not user.enabled:
                continue
            for secret in user.secrets:
                if secret.enabled:
                    entries.append((self._telemt_username(user, secret), user, secret))
        return entries

    def enabled_secret_count(self) -> int:
        return self.inventory.enabled_secret_count()

    def runtime_prerequisites_ready(self) -> bool:
        return (
            self.paths.binary_file.exists()
            and self.paths.telemt_config_file.exists()
            and self.paths.telemt_config_file.stat().st_size > 0
            and self.enabled_secret_count() > 0
        )

    def build_exec_args(self, settings: AppSettings) -> list[str]:
        if not self.paths.binary_file.exists():
            raise AppError(f"binary not found: {self.paths.binary_file}")
        if not self.paths.telemt_config_file.exists() or self.paths.telemt_config_file.stat().st_size == 0:
            raise AppError(f"telemt config is empty: {self.paths.telemt_config_file}")
        if self.enabled_secret_count() == 0:
            raise AppError("no enabled secrets available for telemt")
        return [str(self.paths.binary_file), str(self.paths.telemt_config_file)]

    def write_runtime_snapshot(self, settings: AppSettings, exec_args: list[str]) -> None:
        self.storage.save_json(
            self.paths.runtime_file,
            {
                "schema_version": 1,
                "backend": "telemt",
                "enabled_secret_count": self.enabled_secret_count(),
                "exec_args": exec_args,
                "config_file": str(self.paths.telemt_config_file),
                "fake_tls_domain": settings.fake_tls_domain,
                "mt_port": settings.mt_port,
                "stats_port": settings.stats_port,
                "workers": settings.workers,
            },
        )

    def reconcile(self, settings: AppSettings, systemd: SystemdService, *, restart: bool = True) -> int:
        self.rebuild_runtime_config(settings)
        enabled_count = self.enabled_secret_count()
        prerequisites_ready = enabled_count > 0 and self.runtime_prerequisites_ready()
        if systemd.is_installed():
            if enabled_count == 0:
                systemd.stop()
            elif restart and prerequisites_ready:
                systemd.restart()
        exec_args = self.build_exec_args(settings) if prerequisites_ready else []
        self.write_runtime_snapshot(settings, exec_args)
        return enabled_count

    def exec_proxy(self, settings: AppSettings) -> int:
        args = self.build_exec_args(settings)
        self.write_runtime_snapshot(settings, args)
        try:
            os.execv(args[0], args)
        except OSError as exc:
            raise ServiceError(f"failed to exec telemt binary: {exc}") from exc
        return 0

    def render_config(self, settings: AppSettings) -> str:
        tls_enabled = bool(settings.fake_tls_domain)
        lines = [
            "# Managed by mtp-manager. Manual edits may be overwritten.",
            "[general]",
            "use_middle_proxy = true",
        ]
        if settings.ad_tag:
            lines.append(f"ad_tag = {self._toml_string(settings.ad_tag)}")
        lines.extend(
            [
                'log_level = "normal"',
                "",
                "[general.modes]",
                "classic = true",
                "secure = true",
                f"tls = {self._toml_bool(tls_enabled)}",
                "",
                "[general.links]",
                'show = "*"',
                f"public_port = {settings.mt_port}",
                "",
                "[server]",
                f"port = {settings.mt_port}",
                "",
                "[server.api]",
                "enabled = true",
                f"listen = {self._toml_string(f'127.0.0.1:{settings.stats_port}')}",
                'whitelist = ["127.0.0.0/8"]',
                "minimal_runtime_enabled = false",
                "minimal_runtime_cache_ttl_ms = 1000",
                "",
                "[[server.listeners]]",
                'ip = "0.0.0.0"',
            ]
        )
        if tls_enabled:
            lines.extend(
                [
                    "",
                    "[censorship]",
                    f"tls_domain = {self._toml_string(settings.fake_tls_domain)}",
                    "mask = true",
                    "tls_emulation = true",
                    f"tls_front_dir = {self._toml_string(self.paths.tls_front_dir.name)}",
                ]
            )
        lines.extend(["", "[access.users]"])
        for username, _, secret in self._enabled_entries():
            lines.append(f"{self._toml_key(username)} = {self._toml_string(secret.raw_secret)}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _telemt_username(user: UserRecord, secret: SecretRecord) -> str:
        return f"{user.name}__secret_{secret.id}"

    @staticmethod
    def _toml_bool(value: bool) -> str:
        return "true" if value else "false"

    @staticmethod
    def _toml_string(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _toml_key(self, value: str) -> str:
        return self._toml_string(value)
