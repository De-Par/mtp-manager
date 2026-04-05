from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from errors import AppError
from i18n import Translator
from models.export import ExportBundle
from models.health import HealthReport
from models.secret import SecretRecord, UserRecord
from models.settings import AppSettings
from paths import ProjectPaths
from services import CleanupService, DiagnosticsService, ExportService, InstallService, InventoryService, ProxyRuntimeService, SettingsService, SystemdService


@dataclass(slots=True)
class DashboardViewModel:
    service_status: str
    public_ip: str
    telemt_version: str
    mt_port: int
    stats_port: int
    workers: int
    fake_tls_domain: str
    users_count: int
    secrets_count: int


class AppController:
    def __init__(
        self,
        translator: Translator,
        settings_service: SettingsService,
        inventory_service: InventoryService,
        export_service: ExportService,
        diagnostics_service: DiagnosticsService,
        install_service: InstallService,
        cleanup_service: CleanupService,
        runtime_service: ProxyRuntimeService,
        systemd_service: SystemdService,
        paths: ProjectPaths,
    ) -> None:
        self.translator = translator
        self.settings_service = settings_service
        self.inventory_service = inventory_service
        self.export_service = export_service
        self.diagnostics_service = diagnostics_service
        self.install_service = install_service
        self.cleanup_service = cleanup_service
        self.runtime_service = runtime_service
        self.systemd_service = systemd_service
        self.paths = paths

    @property
    def script_path(self) -> Path:
        return self.paths.self_install_path

    def load_settings(self) -> AppSettings:
        return self.settings_service.load()

    def save_settings(self, settings: AppSettings) -> AppSettings:
        self.translator.set_lang(settings.ui_lang)
        return self.settings_service.save(settings)

    def update_settings(
        self,
        *,
        mt_port: int | None = None,
        stats_port: int | None = None,
        workers: int | None = None,
        fake_tls_domain: str | None = None,
        ad_tag: str | None = None,
        telemt_ref: str | None = None,
        ui_lang: str | None = None,
    ) -> AppSettings:
        current = self.load_settings()
        changes: dict[str, object] = {}
        if mt_port is not None:
            changes["mt_port"] = mt_port
        if stats_port is not None:
            changes["stats_port"] = stats_port
        if workers is not None:
            changes["workers"] = workers
        if fake_tls_domain is not None:
            changes["fake_tls_domain"] = fake_tls_domain.strip()
        if ad_tag is not None:
            changes["ad_tag"] = ad_tag.strip()
        if telemt_ref is not None:
            changes["telemt_ref"] = telemt_ref.strip()
        if ui_lang is not None:
            changes["ui_lang"] = ui_lang.strip().lower()
        updated = self.settings_service.update(**changes)
        if updated.ui_lang != current.ui_lang:
            self.translator.set_lang(updated.ui_lang)
        return updated

    def dashboard(self) -> DashboardViewModel:
        settings = self.load_settings()
        users = self.inventory_service.load_users()
        report = self.diagnostics_service.build_report(settings)
        service_status = next((check.value for check in report.checks if check.key == "service_status"), "unknown")
        public_ip = next((check.value for check in report.checks if check.key == "public_ip"), "unknown")
        telemt_version = next((check.value for check in report.checks if check.key == "telemt_version"), "unknown")
        enabled_secrets = self.runtime_service.enabled_secret_count()
        if enabled_secrets == 0:
            service_status = "no-secrets"
        elif not self.runtime_service.runtime_prerequisites_ready():
            service_status = "not-ready"
        return DashboardViewModel(
            service_status=service_status,
            public_ip=public_ip,
            telemt_version=telemt_version,
            mt_port=settings.mt_port,
            stats_port=settings.stats_port,
            workers=settings.workers,
            fake_tls_domain=settings.fake_tls_domain,
            users_count=len(users),
            secrets_count=sum(len(user.secrets) for user in users),
        )

    def diagnostics(self) -> HealthReport:
        return self.diagnostics_service.build_report(self.load_settings())

    def list_users(self) -> list[UserRecord]:
        return self.inventory_service.load_users()

    def get_user(self, user_name: str | None) -> UserRecord | None:
        if not user_name:
            return None
        try:
            return self.inventory_service.get_user(user_name)
        except AppError:
            return None

    def get_secret(self, secret_id: int | None) -> SecretRecord | None:
        if secret_id is None:
            return None
        try:
            _, secret = self.inventory_service.get_secret(secret_id)
            return secret
        except AppError:
            return None

    def selected_detail_text(self, user_name: str | None, secret_id: int | None) -> str:
        user = self.get_user(user_name)
        if user is None:
            return "No user selected."
        lines = [
            f"User: {user.name}",
            f"User enabled: {'on' if user.enabled else 'off'}",
            f"Secrets total: {len(user.secrets)}",
        ]
        secret = self.get_secret(secret_id)
        if secret is None:
            lines.append("No secret selected")
            return "\n".join(lines)
        lines.extend(
            [
                "",
                f"Secret ID: {secret.id}",
                f"Secret enabled: {'on' if secret.enabled else 'off'}",
                f"Raw: {secret.raw_secret}",
                f"Created: {secret.created_at or '-'}",
                f"Note: {secret.note or '-'}",
            ]
        )
        settings = self.load_settings()
        report = self.diagnostics_service.build_report(settings)
        host = next((check.value for check in report.checks if check.key == "public_ip"), "") or "<public-ip>"
        bundle = self.export_service.build_bundle(host, settings, user, secret)
        lines.extend(
            [
                "",
                "Links",
                f"DD: {bundle.links.padded_secret}",
                f"EE: {bundle.links.fake_tls_secret or 'disabled'}",
                f"tg raw: {bundle.links.tg_raw}",
                f"t.me raw: {bundle.links.tme_raw}",
                f"tg dd: {bundle.links.tg_padded}",
                f"t.me dd: {bundle.links.tme_padded}",
                f"tg ee: {bundle.links.tg_fake_tls or 'disabled'}",
                f"t.me ee: {bundle.links.tme_fake_tls or 'disabled'}",
            ]
        )
        return "\n".join(lines)

    def add_user(self, user_name: str) -> UserRecord:
        return self.inventory_service.add_user(user_name)

    def add_secret(self, user_name: str, note: str = "") -> SecretRecord:
        record = self.inventory_service.add_secret(user_name, note=note)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return record

    def set_user_enabled(self, user_name: str, enabled: bool) -> str:
        changed = self.inventory_service.set_user_enabled(user_name, enabled)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        state = "enabled" if enabled else "disabled"
        return f"User {user_name} {state}; affected secrets: {changed}."

    def rotate_user(self, user_name: str, *, only_enabled: bool = True) -> str:
        changed = self.inventory_service.rotate_user(user_name, only_enabled=only_enabled)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return f"Secrets refreshed for {user_name}; rotated: {changed}."

    def delete_user(self, user_name: str) -> str:
        removed = self.inventory_service.delete_user(user_name)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return f"User {user_name} deleted; removed secrets: {removed}."

    def set_secret_enabled(self, secret_id: int, enabled: bool) -> str:
        self.inventory_service.set_secret_enabled(secret_id, enabled)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        state = "enabled" if enabled else "disabled"
        return f"Secret #{secret_id} {state}."

    def rotate_secret(self, secret_id: int) -> str:
        rotated = self.inventory_service.rotate_secret(secret_id)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return f"Secret #{rotated.id} refreshed."

    def delete_secret(self, secret_id: int) -> str:
        self.inventory_service.delete_secret(secret_id)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return f"Secret #{secret_id} deleted."

    def selected_user_secret_ids(self, user_name: str | None) -> list[int]:
        if not user_name:
            return []
        user = self.inventory_service.get_user(user_name)
        return [secret.id for secret in user.secrets]

    def selected_or_first_secret_id(self, user_name: str | None, current_secret_id: int | None = None) -> int | None:
        secret_ids = self.selected_user_secret_ids(user_name)
        if not secret_ids:
            return None
        if current_secret_id in secret_ids:
            return current_secret_id
        return secret_ids[0]

    def next_secret_id(self, user_name: str | None, current_secret_id: int | None = None) -> int | None:
        secret_ids = self.selected_user_secret_ids(user_name)
        if not secret_ids:
            return None
        if current_secret_id not in secret_ids:
            return secret_ids[0]
        index = secret_ids.index(current_secret_id)
        return secret_ids[(index + 1) % len(secret_ids)]

    def previous_secret_id(self, user_name: str | None, current_secret_id: int | None = None) -> int | None:
        secret_ids = self.selected_user_secret_ids(user_name)
        if not secret_ids:
            return None
        if current_secret_id not in secret_ids:
            return secret_ids[0]
        index = secret_ids.index(current_secret_id)
        return secret_ids[(index - 1) % len(secret_ids)]

    def selected_or_first_user(self, current: str | None = None) -> str | None:
        users = self.list_users()
        if not users:
            return None
        names = [user.name for user in users]
        if current in names:
            return current
        return names[0]

    def next_user(self, current: str | None = None) -> str | None:
        users = self.list_users()
        if not users:
            return None
        names = [user.name for user in users]
        if current not in names:
            return names[0]
        index = names.index(current)
        return names[(index + 1) % len(names)]

    def previous_user(self, current: str | None = None) -> str | None:
        users = self.list_users()
        if not users:
            return None
        names = [user.name for user in users]
        if current not in names:
            return names[0]
        index = names.index(current)
        return names[(index - 1) % len(names)]

    def run_setup(self, *, source_mode: str = "fresh") -> str:
        settings = self.load_settings()
        if self.systemd_service.is_installed():
            self.install_service.update_source(settings, self.script_path, source_mode="update")
            return "Setup synchronized the existing telemt installation."

        from services.install_service import SetupOptions

        self.install_service.initial_setup(settings, self.script_path, SetupOptions(source_mode=source_mode))
        return "telemt setup completed."

    def run_update(self, *, source_mode: str = "update") -> str:
        self.install_service.update_source(self.load_settings(), self.script_path, source_mode=source_mode)
        return "telemt synchronized with the current target."

    def run_rebuild(self) -> str:
        self.install_service.rebuild_source(self.load_settings())
        return "telemt binary reinstalled."

    def install_telemt_ref(self, ref: str) -> str:
        normalized_ref = ref.strip()
        settings = self.settings_service.update(apply_runtime=False, telemt_ref=normalized_ref)
        if self.systemd_service.is_installed():
            self.install_service.update_source(settings, self.script_path, source_mode="update")
        else:
            from services.install_service import SetupOptions

            self.install_service.initial_setup(settings, self.script_path, SetupOptions(source_mode=settings.source_mode))
        if normalized_ref:
            return f"telemt installed from ref: {normalized_ref}"
        return "telemt installed from latest release."

    def run_reinstall_units(self) -> str:
        self.install_service.reinstall_units(self.script_path)
        return "Systemd units rewritten"

    def service_start(self) -> str:
        self._ensure_service_can_run()
        self.systemd_service.start()
        return "Service started."

    def service_stop(self) -> str:
        self.systemd_service.stop()
        return "Service stopped."

    def service_restart(self) -> str:
        self._ensure_service_can_run()
        self.systemd_service.restart()
        return "Service restarted."

    def service_status_text(self) -> str:
        return self.systemd_service.status().strip() or "No status available."

    def service_logs_text(self) -> str:
        body = self.systemd_service.logs().strip()
        if not body or body == "-- No entries --":
            return "No logs available."
        return body

    def service_unit_preview(self) -> str:
        return self.systemd_service.preview().strip() or "No unit preview available."

    def clear_service_logs(self) -> str:
        self.cleanup_service.clear_service_logs()
        return "Service logs cleared."

    def service_cleanup(self) -> str:
        self.cleanup_service.cleanup_logs()
        self.cleanup_service.cleanup_runtime()
        self.cleanup_service.refresh_runtime_snapshot()
        return "Cleanup finished: logs, caches, temp files, and mtp-manager artifacts cleaned."

    def factory_reset(self, *, remove_swap: bool = False) -> str:
        self.cleanup_service.factory_reset(remove_swap=remove_swap)
        return "Factory reset completed. Managed telemt services and files were removed."

    def set_language(self, lang: str) -> AppSettings:
        return self.update_settings(ui_lang=lang)

    def _ensure_service_can_run(self) -> None:
        settings = self.load_settings()
        self.runtime_service.rebuild_runtime_config(settings)
        enabled_secrets = self.runtime_service.enabled_secret_count()
        if enabled_secrets == 0:
            raise AppError("Enable at least one secret before starting the service.")
        if not self.runtime_service.runtime_prerequisites_ready():
            raise AppError("Run Setup or Apply Changes before starting the service.")
        exec_args = self.runtime_service.build_exec_args(settings)
        self.runtime_service.write_runtime_snapshot(settings, exec_args)

    def export_for_user(self, user_name: str) -> list[ExportBundle]:
        settings = self.load_settings()
        report = self.diagnostics_service.build_report(settings)
        host = next((check.value for check in report.checks if check.key == "public_ip"), "") or "<public-ip>"
        bundles: list[ExportBundle] = []
        for user in self.inventory_service.load_users():
            if user.name != user_name:
                continue
            for secret in user.secrets:
                bundles.append(self.export_service.build_bundle(host, settings, user, secret))
        return bundles

    def export_text_for_user(self, user_name: str | None) -> str:
        if not user_name:
            return "No user selected."
        bundles = self.export_for_user(user_name)
        if not bundles:
            return "No exportable secrets available."
        return self.export_service.render_bundles(bundles)

    def export_selected_user_to_file(self, user_name: str | None) -> str:
        if not user_name:
            return "No user selected."
        bundles = self.export_for_user(user_name)
        if not bundles:
            return "No exportable secrets available."
        path = self.export_service.export_bundles_to_file(bundles, self.paths.export_file)
        return f"Export saved to {path}."
