from __future__ import annotations

import os

from errors import AppError, ServiceError
from infra.storage import JsonStorage
from models.settings import AppSettings
from paths import ProjectPaths
from services.inventory_service import InventoryService
from services.systemd_service import SystemdService


class ProxyRuntimeService:
    def __init__(self, storage: JsonStorage, inventory: InventoryService, paths: ProjectPaths) -> None:
        self.storage = storage
        self.inventory = inventory
        self.paths = paths

    def rebuild_secrets_file(self) -> str:
        lines = []
        for user in self.inventory.load_users():
            if not user.enabled:
                continue
            for secret in user.secrets:
                if secret.enabled:
                    lines.append(secret.raw_secret)
        body = "\n".join(lines) + ("\n" if lines else "")
        self.storage.save_text(self.paths.secrets_file, body)
        return body

    def enabled_secret_count(self) -> int:
        return self.inventory.enabled_secret_count()

    def runtime_prerequisites_ready(self) -> bool:
        return (
            self.paths.binary_file.exists()
            and self.paths.proxy_secret_file.exists()
            and self.paths.proxy_config_file.exists()
            and self.paths.secrets_file.exists()
            and self.paths.secrets_file.stat().st_size > 0
        )

    def build_exec_args(self, settings: AppSettings) -> list[str]:
        if not self.paths.binary_file.exists():
            raise AppError(f"binary not found: {self.paths.binary_file}")
        if not self.paths.proxy_secret_file.exists():
            raise AppError(f"proxy secret file not found: {self.paths.proxy_secret_file}")
        if not self.paths.proxy_config_file.exists():
            raise AppError(f"proxy config file not found: {self.paths.proxy_config_file}")
        if not self.paths.secrets_file.exists() or self.paths.secrets_file.stat().st_size == 0:
            raise AppError(f"secrets file is empty: {self.paths.secrets_file}")
        args = [
            str(self.paths.binary_file),
            "-u",
            "nobody",
            "-p",
            str(settings.stats_port),
            "-H",
            str(settings.mt_port),
        ]
        for line in self.paths.secrets_file.read_text(encoding="utf-8").splitlines():
            secret = line.strip()
            if secret:
                args.extend(["-S", secret])
        args.extend(["--aes-pwd", str(self.paths.proxy_secret_file), str(self.paths.proxy_config_file)])
        if settings.workers > 0 and not settings.fake_tls_domain:
            args.extend(["-M", str(settings.workers)])
        if settings.fake_tls_domain:
            args.extend(["--domain", settings.fake_tls_domain])
        if settings.ad_tag:
            args.extend(["-P", settings.ad_tag])
        return args

    def write_runtime_snapshot(self, settings: AppSettings, exec_args: list[str]) -> None:
        self.storage.save_json(
            self.paths.runtime_file,
            {
                "schema_version": 1,
                "enabled_secret_count": self.enabled_secret_count(),
                "exec_args": exec_args,
                "fake_tls_domain": settings.fake_tls_domain,
                "mt_port": settings.mt_port,
                "stats_port": settings.stats_port,
                "workers": settings.workers,
            },
        )

    def reconcile(self, settings: AppSettings, systemd: SystemdService, *, restart: bool = True) -> int:
        self.rebuild_secrets_file()
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
            raise ServiceError(f"failed to exec MTProxy binary: {exc}") from exc
        return 0
