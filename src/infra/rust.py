from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request

from errors import ServiceError
from infra.shell import ShellRunner


def rust_version(value: str) -> tuple[int, ...]:
    match = re.search(r"(?:rustc\s+)?(\d+\.\d+(?:\.\d+)?)", value)
    return tuple(int(part) for part in match[1].split(".")) if match else ()


def ensure_cargo(shell: ShellRunner, state_dir: Path, required: str) -> tuple[str, dict[str, str] | None]:
    """Use a suitable system compiler, or provision an isolated stable toolchain."""
    minimum = rust_version(required)
    if shutil.which("rustc") and shutil.which("cargo"):
        result = shell.run(["rustc", "--version"], check=False)
        if result.returncode == 0 and rust_version(result.stdout) >= minimum:
            return "cargo", None
    cargo_home = state_dir / "cargo"
    env = dict(os.environ)
    env.update({
        "CARGO_HOME": str(cargo_home), "RUSTUP_HOME": str(state_dir / "rustup"),
        "PATH": str(cargo_home / "bin") + os.pathsep + env.get("PATH", ""),
        "RUSTUP_INIT_SKIP_PATH_CHECK": "yes",
    })
    compiler = cargo_home / "bin" / "rustc"
    rustup = cargo_home / "bin" / "rustup"
    if compiler.exists():
        result = shell.run([str(compiler), "--version"], env=env, check=False)
        if result.returncode == 0 and rust_version(result.stdout) >= minimum:
            return str(cargo_home / "bin" / "cargo"), env
    if rustup.exists():
        shell.run([str(rustup), "toolchain", "install", "stable", "--profile", "minimal"], env=env)
        shell.run([str(rustup), "default", "stable"], env=env)
    else:
        machine = os.uname().machine.lower()
        arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
        target = f"{arch}-unknown-linux-gnu"
        url = f"https://static.rust-lang.org/rustup/dist/{target}/rustup-init"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        with urllib.request.urlopen(url + ".sha256", timeout=30) as response:
            expected = response.read().decode().split()[0]
        if hashlib.sha256(data).hexdigest() != expected:
            raise ServiceError("rust_toolchain_checksum_failed")
        with tempfile.TemporaryDirectory(prefix="mtp-manager-rust-") as temporary:
            installer = Path(temporary) / "rustup-init"
            installer.write_bytes(data)
            installer.chmod(0o755)
            shell.run([str(installer), "-y", "--no-modify-path", "--profile", "minimal", "--default-toolchain", "stable"], env=env)
    result = shell.run([str(compiler), "--version"], env=env)
    if rust_version(result.stdout) < minimum:
        raise ServiceError("rust_toolchain_too_old")
    return str(cargo_home / "bin" / "cargo"), env
