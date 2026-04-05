from __future__ import annotations

from dataclasses import dataclass

from errors import PlatformError
from .distro import DistroInfo, DistroProbe
from .shell import ShellRunner


@dataclass(frozen=True, slots=True)
class PackageSet:
    runtime: tuple[str, ...]
    build: tuple[str, ...]


class PackageManager:
    PACKAGE_SETS = {
        "debian": PackageSet(
            runtime=("curl", "ca-certificates", "ufw"),
            build=("cargo", "rustc", "build-essential", "pkg-config"),
        ),
        "fedora": PackageSet(
            runtime=("curl", "ca-certificates", "firewalld"),
            build=("cargo", "rust", "gcc", "make", "pkgconf-pkg-config"),
        ),
        "arch": PackageSet(
            runtime=("curl", "ca-certificates", "iptables-nft"),
            build=("cargo", "rust", "base-devel", "pkgconf"),
        ),
    }

    def __init__(self, shell: ShellRunner, distro: DistroInfo | DistroProbe) -> None:
        self.shell = shell
        self.distro = distro

    @property
    def distro_info(self) -> DistroInfo:
        if isinstance(self.distro, DistroProbe):
            return self.distro.detect()
        return self.distro

    @property
    def package_set(self) -> PackageSet:
        try:
            return self.PACKAGE_SETS[self.distro_info.family]
        except KeyError as exc:
            raise PlatformError(f"unsupported package manager family: {self.distro_info.family}") from exc

    def install(self, packages: list[str]) -> None:
        if not packages:
            return
        distro = self.distro_info
        if distro.family == "debian":
            self.shell.run(["apt-get", "update"])
            self.shell.run(["apt-get", "install", "-y", *packages])
            return
        if distro.family == "fedora":
            self.shell.run(["dnf", "install", "-y", *packages])
            return
        if distro.family == "arch":
            self.shell.run(["pacman", "-Sy", "--noconfirm", *packages])
            return
        raise PlatformError(f"unsupported package manager family: {distro.family}")

    def cleanup(self) -> None:
        distro = self.distro_info
        if distro.family == "debian":
            self.shell.run(["apt-get", "autoremove", "--purge", "-y"], check=False)
            self.shell.run(["apt-get", "clean"], check=False)
            self.shell.run(["apt-get", "autoclean"], check=False)
            return
        if distro.family == "fedora":
            self.shell.run(["dnf", "autoremove", "-y"], check=False)
            self.shell.run(["dnf", "clean", "all"], check=False)
            return
        if distro.family == "arch":
            self.shell.run(["pacman", "-Sc", "--noconfirm"], check=False)
            return
