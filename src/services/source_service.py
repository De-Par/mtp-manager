from __future__ import annotations

import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request

from errors import SourceBuildRequiredError
from infra.shell import ShellRunner
from paths import ProjectPaths


class SourceService:
    REPO_URL = "https://github.com/telemt/telemt"
    BIN_NAME = "telemt"

    def __init__(self, shell: ShellRunner, paths: ProjectPaths) -> None:
        self.shell = shell
        self.paths = paths

    def install(self, mode: str, ref: str = "", *, allow_build: bool = True) -> Path:
        normalized_ref = ref.strip()
        if mode == "fresh" and self.paths.mt_dir.exists():
            shutil.rmtree(self.paths.mt_dir)
        if mode == "reuse" and self.paths.binary_file.exists() and not normalized_ref:
            return self.paths.binary_file

        self.paths.bin_dir.mkdir(parents=True, exist_ok=True)
        if not normalized_ref:
            self._install_release_binary()
            return self.paths.binary_file
        try:
            self._install_release_binary(normalized_ref)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            if not allow_build:
                raise SourceBuildRequiredError(f"telemt ref requires source build: {normalized_ref}") from exc
            self._build_from_source(normalized_ref)
        return self.paths.binary_file

    def _install_release_binary(self, ref: str | None = None) -> Path:
        asset_name = self._asset_name()
        if ref:
            archive_url = f"{self.REPO_URL}/releases/download/{ref}/{asset_name}"
        else:
            archive_url = f"{self.REPO_URL}/releases/latest/download/{asset_name}"

        with tempfile.TemporaryDirectory(prefix="telemt-release-") as temp_dir:
            archive_path = Path(temp_dir) / asset_name
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

    def _build_from_source(self, ref: str) -> Path:
        archive_url = f"https://codeload.github.com/telemt/telemt/tar.gz/{ref}"
        with tempfile.TemporaryDirectory(prefix="telemt-source-") as temp_dir:
            temp_root = Path(temp_dir)
            archive_path = temp_root / "telemt-source.tar.gz"
            with urllib.request.urlopen(archive_url, timeout=60) as response:
                archive_path.write_bytes(response.read())
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(temp_root)
            source_root = next((item for item in temp_root.iterdir() if item.is_dir()), None)
            if source_root is None:
                raise FileNotFoundError(f"failed to extract telemt source for ref: {ref}")
            self.shell.run(["cargo", "build", "--release"], cwd=source_root)
            built_binary = source_root / "target" / "release" / self.BIN_NAME
            if not built_binary.exists():
                raise FileNotFoundError(f"built telemt binary not found for ref: {ref}")
            self.paths.binary_file.write_bytes(built_binary.read_bytes())
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
