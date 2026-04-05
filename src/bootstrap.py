from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from controller import AppController
from i18n import Translator
from infra import DistroProbe, FirewallManager, JsonStorage, LocaleManager, PackageManager, PublicIpResolver, ShellRunner, SystemdManager
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


def _move_if_missing(source: Path, target: Path) -> None:
    if not source.exists() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def _merge_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return
    if source.is_file():
        return
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            _merge_tree(item, destination)
        elif not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(destination))
    try:
        source.rmdir()
    except OSError:
        pass


def migrate_legacy_layout(paths: ProjectPaths) -> None:
    _merge_tree(paths.legacy_mt_dir, paths.mt_dir)
    _merge_tree(paths.legacy_conf_dir, paths.conf_dir)
    _merge_tree(paths.legacy_data_dir, paths.data_dir)
    _move_if_missing(paths.legacy_lock_file, paths.lock_file)
    _move_if_missing(paths.legacy_export_file, paths.export_file)
    _move_if_missing(paths.legacy_sysctl_file, paths.sysctl_file)


def build_container() -> AppContainer:
    paths = default_paths()
    shell = ShellRunner()
    storage = JsonStorage()
    migrate_legacy_layout(paths)
    distro_probe = DistroProbe()
    packages = PackageManager(shell, distro_probe)
    firewall = FirewallManager(shell, distro_probe)
    inventory_service = InventoryService(storage, paths)
    systemd_manager = SystemdManager(shell)
    systemd_service = SystemdService(systemd_manager, storage, paths)
    network_service = NetworkService(PublicIpResolver())
    runtime_service = ProxyRuntimeService(storage, inventory_service, paths)
    settings_service = SettingsService(storage, paths, runtime=runtime_service, systemd=systemd_service, firewall=firewall)
    translator = Translator(settings_service.load().ui_lang)
    diagnostics_service = DiagnosticsService(network_service, inventory_service, systemd_service, shell, paths)
    export_service = ExportService()
    source_service = SourceService(shell, paths)
    install_service = InstallService(
        shell=shell,
        distro=distro_probe,
        packages=packages,
        locale=LocaleManager(shell, paths.locale_file),
        source=source_service,
        runtime=runtime_service,
        systemd=systemd_service,
        firewall=firewall,
    )
    cleanup_service = CleanupService(systemd_manager, storage, paths, packages)
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
