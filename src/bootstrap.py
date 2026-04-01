from __future__ import annotations

from dataclasses import dataclass

from controller import AppController
from i18n import Translator
from infra import DistroProbe, JsonStorage, LocaleManager, PublicIpResolver, ShellRunner, SystemdManager, UfwManager
from paths import ProjectPaths, default_paths
from services import (
    CleanupService,
    DiagnosticsService,
    ExportService,
    InstallService,
    InventoryService,
    NetworkService,
    ProxyRuntimeService,
    SettingsService,
    SourceService,
    SystemdService,
)
from ui.backend import UIBackend
from ui.textual_app import TextualUI


@dataclass(slots=True)
class AppContainer:
    controller: AppController
    ui: UIBackend
    paths: ProjectPaths
    cleanup_service: CleanupService
    install_service: InstallService
    settings_service: SettingsService
    inventory_service: InventoryService
    runtime_service: ProxyRuntimeService
    network_service: NetworkService
    systemd_service: SystemdService


def build_container() -> AppContainer:
    paths = default_paths()
    shell = ShellRunner()
    storage = JsonStorage()
    inventory_service = InventoryService(storage, paths)
    systemd_manager = SystemdManager(shell)
    systemd_service = SystemdService(systemd_manager, storage, paths)
    network_service = NetworkService(PublicIpResolver())
    runtime_service = ProxyRuntimeService(storage, inventory_service, paths)
    settings_service = SettingsService(storage, paths, runtime=runtime_service, systemd=systemd_service, ufw=UfwManager(shell))
    translator = Translator(settings_service.load().ui_lang)
    diagnostics_service = DiagnosticsService(network_service, inventory_service, systemd_service)
    export_service = ExportService()
    source_service = SourceService(shell, paths)
    install_service = InstallService(
        shell=shell,
        distro=DistroProbe(),
        locale=LocaleManager(shell, paths.locale_file),
        source=source_service,
        network=network_service,
        runtime=runtime_service,
        systemd=systemd_service,
        ufw=UfwManager(shell),
    )
    cleanup_service = CleanupService(systemd_manager, storage, paths)
    controller = AppController(
        translator=translator,
        settings_service=settings_service,
        inventory_service=inventory_service,
        export_service=export_service,
        diagnostics_service=diagnostics_service,
        install_service=install_service,
        cleanup_service=cleanup_service,
        runtime_service=runtime_service,
        systemd_service=systemd_service,
        paths=paths,
    )
    ui = TextualUI()
    return AppContainer(
        controller=controller,
        ui=ui,
        paths=paths,
        cleanup_service=cleanup_service,
        install_service=install_service,
        settings_service=settings_service,
        inventory_service=inventory_service,
        runtime_service=runtime_service,
        network_service=network_service,
        systemd_service=systemd_service,
    )
