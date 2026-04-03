from __future__ import annotations

import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

from infra.shell import ShellRunner
from paths import ProjectPaths


class SourceService:
    REPO_URL = "https://github.com/telemt/telemt"
    BIN_NAME = "telemt"

    def __init__(self, shell: ShellRunner, paths: ProjectPaths) -> None:
        self.shell = shell
        self.paths = paths

    def install(self, mode: str) -> Path:
        if mode == "fresh" and self.paths.mt_dir.exists():
            shutil.rmtree(self.paths.mt_dir)
        if mode == "reuse" and self.paths.binary_file.exists():
            return self.paths.binary_file

        archive_url = f"{self.REPO_URL}/releases/latest/download/{self._asset_name()}"
        self.paths.bin_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="telemt-release-") as temp_dir:
            archive_path = Path(temp_dir) / self._asset_name()
            with urllib.request.urlopen(archive_url, timeout=60) as response:
                archive_path.write_bytes(response.read())

            with tarfile.open(archive_path, "r:gz") as archive:
                binary_member = next(
                    (
                        member
                        for member in archive.getmembers()
                        if member.isfile() and Path(member.name).name == self.BIN_NAME
                    ),
                    None,
                )
                if binary_member is None:
                    raise FileNotFoundError(f"{self.BIN_NAME} was not found in {archive_url}")
                extracted = archive.extractfile(binary_member)
                if extracted is None:
                    raise FileNotFoundError(f"failed to extract {self.BIN_NAME} from archive")
                self.paths.binary_file.write_bytes(extracted.read())

        os.chmod(self.paths.binary_file, 0o755)
        return self.paths.binary_file

    def _asset_name(self) -> str:
        return f"{self.BIN_NAME}-{self._detect_arch()}-linux-{self._detect_libc()}.tar.gz"

    @staticmethod
    def _detect_arch() -> str:
        machine = os.uname().machine.lower()
        if machine in {"x86_64", "amd64"}:
            return "x86_64"
        if machine in {"aarch64", "arm64"}:
            return "aarch64"
        raise RuntimeError(f"unsupported architecture for telemt release: {machine}")

    @staticmethod
    def _detect_libc() -> str:
        if list(Path("/lib").glob("ld-musl-*.so.*")) or list(Path("/lib64").glob("ld-musl-*.so.*")):
            return "musl"
        if Path("/etc/os-release").exists():
            os_release = Path("/etc/os-release").read_text(encoding="utf-8", errors="ignore").lower()
            if 'id="alpine"' in os_release or "id=alpine" in os_release:
                return "musl"
        return "gnu"
