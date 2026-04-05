from __future__ import annotations

import shutil

from .distro import DistroInfo, DistroProbe
from .shell import ShellRunner


class FirewallManager:
    def __init__(self, shell: ShellRunner, distro: DistroInfo | DistroProbe) -> None:
        self.shell = shell
        self.distro = distro

    def allow_tcp(self, port: int) -> None:
        if self._has("ufw"):
            self.shell.run(["ufw", "allow", f"{port}/tcp"], check=False)
            return
        if self._has("firewall-cmd"):
            self.shell.run(["firewall-cmd", "--permanent", "--add-port", f"{port}/tcp"], check=False)
            self.shell.run(["firewall-cmd", "--reload"], check=False)
            return
        if self._has("iptables"):
            self.shell.run(
                ["iptables", "-C", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"],
                check=False,
            )
            self.shell.run(
                ["iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"],
                check=False,
            )

    def delete_allow_tcp(self, port: int) -> None:
        if self._has("ufw"):
            self.shell.run(["ufw", "delete", "allow", f"{port}/tcp"], check=False)
            return
        if self._has("firewall-cmd"):
            self.shell.run(["firewall-cmd", "--permanent", "--remove-port", f"{port}/tcp"], check=False)
            self.shell.run(["firewall-cmd", "--reload"], check=False)
            return
        if self._has("iptables"):
            self.shell.run(
                ["iptables", "-D", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"],
                check=False,
            )

    @staticmethod
    def _has(command: str) -> bool:
        return shutil.which(command) is not None
