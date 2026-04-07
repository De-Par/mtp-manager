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

    def _t(self, key: str, default: str | None = None, **kwargs: object) -> str:
        translated = self.translator.tr(key, **kwargs)
        return default.format(**kwargs) if default is not None and translated == key else translated

    def present_error(self, message: str) -> str:
        if message.startswith("binary not found: "):
            return self._t("binary_not_found", path=message.removeprefix("binary not found: "))
        if message.startswith("telemt config is empty: "):
            return self._t("telemt_config_empty", path=message.removeprefix("telemt config is empty: "))
        if message == "no enabled secrets available for telemt":
            return self._t("no_enabled_secrets_available")
        if message.startswith("duplicate secret id: "):
            return self._t("duplicate_secret_id", id=message.removeprefix("duplicate secret id: "))
        if message.startswith("duplicate secret value for user: "):
            return self._t("duplicate_secret_value_for_user", user=message.removeprefix("duplicate secret value for user: "))
        if message.startswith("user already exists: "):
            return self._t("user_already_exists", user=message.removeprefix("user already exists: "))
        if message.startswith("user not found: "):
            return self._t("user_not_found", user=message.removeprefix("user not found: "))
        if message.startswith("secret not found: "):
            return self._t("secret_not_found", secret_id=message.removeprefix("secret not found: "))
        if message.startswith("no matching secrets for user: "):
            return self._t("no_matching_secrets_for_user", user=message.removeprefix("no matching secrets for user: "))
        if message.startswith("failed to exec telemt binary: "):
            return self._t("failed_to_exec_telemt", error=message.removeprefix("failed to exec telemt binary: "))
        if message.startswith("unsupported architecture for telemt release: "):
            return self._t("unsupported_architecture", arch=message.removeprefix("unsupported architecture for telemt release: "))
        if message.startswith("telemt ref requires source build: "):
            return self._t("source_build_required", ref=message.removeprefix("telemt ref requires source build: "))
        if " was not found in " in message:
            binary, url = message.split(" was not found in ", 1)
            return self._t("binary_missing_in_archive", binary=binary, url=url)
        if message.startswith("failed to extract ") and " from archive" in message:
            binary = message.removeprefix("failed to extract ").removesuffix(" from archive")
            return self._t("failed_to_extract_binary", binary=binary)
        if message.startswith("failed to extract telemt source for ref: "):
            return self._t("failed_to_extract_source", ref=message.removeprefix("failed to extract telemt source for ref: "))
        if message.startswith("built telemt binary not found for ref: "):
            return self._t("built_binary_not_found", ref=message.removeprefix("built telemt binary not found for ref: "))
        if message.startswith("invalid literal for int()"):
            return self._t("invalid_integer_field", field=self._t("proxy_port"))
        if message.startswith("mt_port must be in range "):
            return self._t("port_out_of_range", field=self._t("proxy_port"), min=1, max=65535)
        if message.startswith("stats_port must be in range "):
            return self._t("port_out_of_range", field=self._t("api_port"), min=1, max=65535)
        if message == "workers must be >= 0":
            return self._t("workers_out_of_range")
        if message == "ui_lang must be 'ru' or 'en'":
            return self._t("ui_lang_invalid")
        if message == "fake_tls_domain must be a valid domain name":
            return self._t("fake_tls_domain_invalid")
        if message == "ad_tag must be a 32-character hexadecimal string":
            return self._t("ad_tag_invalid")
        if message == "telemt_ref must not contain whitespace":
            return self._t("telemt_ref_invalid")
        if message == "source_mode is invalid":
            return self._t("source_mode_invalid")
        if message == "Enable at least one secret before starting the service.":
            return self._t("enable_secret_before_start")
        if message == "Run Setup or Apply Changes before starting the service.":
            return self._t("run_setup_before_start")
        return message

    def _human_state(self, state: str) -> str:
        normalized = state.strip().replace("-", "_").replace(" ", "_").lower()
        return self._t(normalized, default=state)

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
            return self._t("no_user_selected")
        lines = [
            f"{self._t('user_name')}: {user.name}",
            f"{self._t('user_enabled')}: {self._t('on' if user.enabled else 'off')}",
            f"{self._t('secrets_total')}: {len(user.secrets)}",
        ]
        secret = self.get_secret(secret_id)
        if secret is None:
            lines.append(self._t("no_secret_selected"))
            return "\n".join(lines)
        lines.extend(
            [
                "",
                f"{self._t('secret_id')}: {secret.id}",
                f"{self._t('secret_enabled')}: {self._t('on' if secret.enabled else 'off')}",
                f"{self._t('raw_secret')}: {secret.raw_secret}",
                f"{self._t('created_at')}: {secret.created_at or '-'}",
                f"{self._t('note')}: {secret.note or '-'}",
            ]
        )
        settings = self.load_settings()
        report = self.diagnostics_service.build_report(settings)
        host = next((check.value for check in report.checks if check.key == "public_ip"), "") or "<public-ip>"
        bundle = self.export_service.build_bundle(host, settings, user, secret)
        lines.extend(
            [
                "",
                self._t("links"),
                f"DD: {bundle.links.padded_secret}",
                f"EE: {bundle.links.fake_tls_secret or self._t('disabled')}",
                f"{self._t('tg_raw')}: {bundle.links.tg_raw}",
                f"{self._t('tme_raw')}: {bundle.links.tme_raw}",
                f"{self._t('tg_dd')}: {bundle.links.tg_padded}",
                f"{self._t('tme_dd')}: {bundle.links.tme_padded}",
                f"{self._t('tg_ee')}: {bundle.links.tg_fake_tls or self._t('disabled')}",
                f"{self._t('tme_ee')}: {bundle.links.tme_fake_tls or self._t('disabled')}",
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
        return self._t("user_state_changed", user=user_name, state=self._t("enabled" if enabled else "disabled"), count=changed)

    def rotate_user(self, user_name: str, *, only_enabled: bool = True) -> str:
        changed = self.inventory_service.rotate_user(user_name, only_enabled=only_enabled)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return self._t("user_rotated", user=user_name, count=changed)

    def delete_user(self, user_name: str) -> str:
        removed = self.inventory_service.delete_user(user_name)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return self._t("user_deleted", user=user_name, count=removed)

    def set_secret_enabled(self, secret_id: int, enabled: bool) -> str:
        self.inventory_service.set_secret_enabled(secret_id, enabled)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return self._t("secret_state_changed", secret_id=secret_id, state=self._t("enabled" if enabled else "disabled"))

    def rotate_secret(self, secret_id: int) -> str:
        rotated = self.inventory_service.rotate_secret(secret_id)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return self._t("secret_rotated", secret_id=rotated.id)

    def delete_secret(self, secret_id: int) -> str:
        self.inventory_service.delete_secret(secret_id)
        self.runtime_service.reconcile(self.load_settings(), self.systemd_service, restart=True)
        return self._t("secret_deleted", secret_id=secret_id)

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
            return self._t("setup_synced_existing")

        from services.install_service import SetupOptions

        self.install_service.initial_setup(settings, self.script_path, SetupOptions(source_mode=source_mode))
        return self._t("setup_completed")

    def run_update(self, *, source_mode: str = "update") -> str:
        self.install_service.update_source(self.load_settings(), self.script_path, source_mode=source_mode)
        return self._t("update_completed")

    def run_rebuild(self) -> str:
        self.install_service.rebuild_source(self.load_settings())
        return self._t("rebuild_completed")

    def install_telemt_ref(self, ref: str) -> str:
        normalized_ref = ref.strip()
        settings = self.settings_service.update(apply_runtime=False, telemt_ref=normalized_ref)
        if self.systemd_service.is_installed():
            self.install_service.update_source(settings, self.script_path, source_mode="update")
        else:
            from services.install_service import SetupOptions

            self.install_service.initial_setup(settings, self.script_path, SetupOptions(source_mode=settings.source_mode))
        if normalized_ref:
            return self._t("install_ref_completed", ref=normalized_ref)
        return self._t("install_latest_completed")

    def run_reinstall_units(self) -> str:
        self.install_service.reinstall_units(self.script_path)
        return self._t("units_reinstalled")

    def service_start(self) -> str:
        self._ensure_service_can_run()
        self.systemd_service.start()
        return self._t("service_started")

    def service_stop(self) -> str:
        self.systemd_service.stop()
        return self._t("service_stopped")

    def service_restart(self) -> str:
        self._ensure_service_can_run()
        self.systemd_service.restart()
        return self._t("service_restarted")

    def service_status_text(self) -> str:
        return self.systemd_service.status().strip() or self._t("no_status_available")

    def service_logs_text(self) -> str:
        body = self.systemd_service.logs().strip()
        if not body or body == "-- No entries --":
            return self._t("no_logs_available")
        return body

    def service_unit_preview(self) -> str:
        return self.systemd_service.preview().strip() or self._t("no_unit_preview_available")

    def clear_service_logs(self) -> str:
        self.cleanup_service.clear_service_logs()
        return self._t("service_logs_cleared")

    def service_cleanup(self) -> str:
        self.cleanup_service.cleanup_logs()
        self.cleanup_service.cleanup_runtime()
        self.cleanup_service.refresh_runtime_snapshot()
        return self._t("cleanup_finished")

    def factory_reset(self, *, remove_swap: bool = False) -> str:
        self.cleanup_service.factory_reset(remove_swap=remove_swap)
        return self._t("factory_reset_completed")

    def set_language(self, lang: str) -> AppSettings:
        return self.update_settings(ui_lang=lang)

    def _ensure_service_can_run(self) -> None:
        settings = self.load_settings()
        self.runtime_service.rebuild_runtime_config(settings)
        enabled_secrets = self.runtime_service.enabled_secret_count()
        if enabled_secrets == 0:
            raise AppError(self._t("enable_secret_before_start"))
        if not self.runtime_service.runtime_prerequisites_ready():
            raise AppError(self._t("run_setup_before_start"))
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
            return self._t("no_user_selected")
        bundles = self.export_for_user(user_name)
        if not bundles:
            return self._t("no_exportable_secrets")
        return self.export_service.render_bundles(bundles, self._t)

    def export_selected_user_to_file(self, user_name: str | None) -> str:
        if not user_name:
            return self._t("no_user_selected")
        bundles = self.export_for_user(user_name)
        if not bundles:
            return self._t("no_exportable_secrets")
        path = self.export_service.export_bundles_to_file(bundles, self.paths.export_file)
        return self._t("export_saved", path=path)
