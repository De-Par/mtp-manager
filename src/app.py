from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys

from bootstrap import build_container
from services.network_service import PROXY_CONFIG_URL


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    use_console = "--console" in argv
    dry_run = "--dry-run" in argv
    container = build_container(dry_run=dry_run, use_console=use_console)
    if len(argv) >= 3 and argv[0] == "internal":
        command = argv[1]
        action = argv[2]
        if command != "run":
            command = f"{argv[0]} {argv[1]}"
        if command == "internal run" and action == "proxy":
            return container.runtime_service.exec_proxy(container.settings_service.load())
        if command == "internal refresh-proxy" and action == "config":
            changed = container.network_service.refresh_if_changed(PROXY_CONFIG_URL, container.paths.proxy_config_file)
            if changed and container.systemd_service.is_installed():
                container.systemd_service.try_restart()
            return 0
        if command == "internal run" and action == "cleanup":
            container.cleanup_service.cleanup_logs()
            container.cleanup_service.cleanup_runtime()
            container.cleanup_service.refresh_runtime_snapshot()
            return 0
    if len(argv) >= 2 and argv[:2] == ["internal", "run-proxy"]:
        return container.runtime_service.exec_proxy(container.settings_service.load())
    if len(argv) >= 2 and argv[:2] == ["internal", "refresh-proxy-config"]:
        changed = container.network_service.refresh_if_changed(PROXY_CONFIG_URL, container.paths.proxy_config_file)
        if changed and container.systemd_service.is_installed():
            container.systemd_service.try_restart()
        return 0
    if len(argv) >= 2 and argv[:2] == ["internal", "run-cleanup"]:
        container.cleanup_service.cleanup_logs()
        container.cleanup_service.cleanup_runtime()
        container.cleanup_service.refresh_runtime_snapshot()
        return 0
    return container.ui.run(container.controller)
