from __future__ import annotations

from .shell import ShellRunner


class SystemdManager:
    def __init__(self, shell: ShellRunner) -> None:
        self.shell = shell

    def start(self, unit: str) -> None:
        self.shell.run(["systemctl", "start", unit])

    def stop(self, unit: str) -> None:
        self.shell.run(["systemctl", "stop", unit], check=False)

    def restart(self, unit: str) -> None:
        self.shell.run(["systemctl", "restart", unit])

    def try_restart(self, unit: str) -> None:
        self.shell.run(["systemctl", "try-restart", unit], check=False)

    def enable(self, unit: str) -> None:
        self.shell.run(["systemctl", "enable", "--now", unit])

    def disable(self, unit: str) -> None:
        self.shell.run(["systemctl", "disable", "--now", unit], check=False)

    def status(self, unit: str) -> str:
        return self.shell.run(["systemctl", "status", unit, "--no-pager", "--full"], check=False).stdout

    def logs(self, unit: str, *, lines: int = 100) -> str:
        return self.shell.run(["journalctl", "-u", unit, "-n", str(lines), "--no-pager"], check=False).stdout

    def cat(self, unit: str) -> str:
        return self.shell.run(["systemctl", "cat", unit], check=False).stdout

    def daemon_reload(self) -> None:
        self.shell.run(["systemctl", "daemon-reload"])

    def is_active(self, unit: str) -> str:
        result = self.shell.run(["systemctl", "is-active", unit], check=False)
        return (result.stdout or result.stderr or "").strip() or "unknown"
