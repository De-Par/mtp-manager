from __future__ import annotations

import shutil

from .shell import ShellRunner


class UfwManager:
    def __init__(self, shell: ShellRunner) -> None:
        self.shell = shell

    def is_available(self) -> bool:
        return shutil.which("ufw") is not None

    def allow_tcp(self, port: int) -> None:
        if self.is_available():
            self.shell.run(["ufw", "allow", f"{port}/tcp"], check=False)

    def delete_allow_tcp(self, port: int) -> None:
        if self.is_available():
            self.shell.run(["ufw", "delete", "allow", f"{port}/tcp"], check=False)
