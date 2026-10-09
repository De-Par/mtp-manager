from __future__ import annotations

import os
import hashlib
import json

from errors import AppError, ServiceError
from infra.storage import JsonStorage
from infra.telemt import supports_web
from models.secret import SecretRecord, UserRecord
from models.settings import AppSettings
from paths import ProjectPaths
from services.inventory_service import InventoryService
from services.systemd_service import SystemdService
from services.web_proxy_service import WebProxyService


class ProxyRuntimeService:
    def __init__(self, storage: JsonStorage, inventory: InventoryService, paths: ProjectPaths) -> None:
        self.storage = storage
        self.inventory = inventory
        self.paths = paths
        self.web = WebProxyService(storage, paths)

    def rebuild_runtime_config(self, settings: AppSettings) -> str:
        self.validate_settings(settings)
        if settings.mtproto_enabled and settings.fake_tls_domain:
            self.paths.tls_front_dir.mkdir(parents=True, exist_ok=True)
        body = self.render_config(settings)
        self.web.prepare(settings)
        self.storage.save_text(self.paths.telemt_config_file, body)
        return body

    def validate_settings(self, settings: AppSettings) -> None:
        settings.validate()
        self.web.validate_decoy(settings)
        if settings.web_enabled and self.paths.binary_file.exists() and not supports_web(self.paths.binary_file):
            raise ServiceError("installed telemt binary lacks WEB support; install a WEB-capable revision such as main")

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
        self.validate_settings(settings)
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
                "proxy_mode": settings.proxy_mode,
                "web_endpoint": settings.web_endpoint if settings.web_enabled else None,
                "web_listen": f"127.0.0.1:{settings.web_port}" if settings.web_enabled else None,
                "web_public_addr": settings.web_public_addr if settings.web_enabled else None,
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
        settings.validate()
        tls_enabled = settings.mtproto_enabled and bool(settings.fake_tls_domain)
        entries = self._enabled_entries()
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
            ]
        )
        if settings.mtproto_enabled:
            lines.extend(["", "[[server.listeners]]", 'ip = "0.0.0.0"', f"port = {settings.mt_port}"])
        if settings.web_enabled:
            lines.extend([
                "", "[[server.listeners]]", 'ip = "127.0.0.1"', f"port = {settings.web_port}",
                'transport = "web"', "proxy_protocol = false", "reuse_allow = false",
                'web_client_ip_source = "x_forwarded_for"', 'web_trusted_proxy_cidrs = ["127.0.0.1/32"]',
                "", "[web]", f"enabled = {self._toml_bool(bool(entries))}", 'carrier = "https"',
                "", "[[web.vhosts]]", f"host = {self._toml_string(settings.web_domain)}",
                f"base_path = {self._toml_string(settings.web_base_path)}",
                f"public_addr = {self._toml_string(settings.web_public_addr)}",
                "", "[web.vhosts.decoy]", 'mode = "static_directory"',
                f"directory = {self._toml_string(str(self.web.decoy_directory(settings)))}", 'index = "index.html"',
            ])
            for username, _, _ in entries:
                for mode in ("plain", "dd"):
                    lines.extend([
                        "", "[[web.vhosts.profiles]]", f"user = {self._toml_string(username)}",
                        f"secret_mode = {self._toml_string(mode)}", "max_sessions = 8",
                        "max_streams = 512", "max_streams_per_session = 64",
                    ])
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
        for username, _, secret in entries:
            lines.append(f"{self._toml_key(username)} = {self._toml_string(secret.raw_secret)}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _telemt_username(user: UserRecord, secret: SecretRecord) -> str:
        username = f"{user.name}__secret_{secret.id}"
        # WEB profile names are limited to 64 UTF-8 bytes by Telemt.
        if len(username.encode("utf-8")) > 64:
            return "user_" + hashlib.sha256(username.encode("utf-8")).hexdigest()[:48]
        return username

    @staticmethod
    def _toml_bool(value: bool) -> str:
        return "true" if value else "false"

    @staticmethod
    def _toml_string(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _toml_key(self, value: str) -> str:
        return self._toml_string(value)
