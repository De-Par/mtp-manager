from __future__ import annotations

from collections.abc import Sequence
import sys

from bootstrap import build_container


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    container = build_container()
    if len(argv) >= 2 and argv[:2] == ["internal", "run-proxy"]:
        return container.runtime_service.exec_proxy(container.settings_service.load())
    if len(argv) >= 2 and argv[:2] == ["internal", "refresh-proxy-config"]:
        container.runtime_service.reconcile(container.settings_service.load(), container.systemd_service, restart=True)
        return 0
    if len(argv) >= 2 and argv[:2] == ["internal", "run-cleanup"]:
        container.cleanup_service.cleanup_logs()
        container.cleanup_service.cleanup_runtime()
        container.cleanup_service.refresh_runtime_snapshot()
        return 0
    return container.ui.run(container.controller)
