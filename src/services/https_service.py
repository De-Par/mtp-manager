from __future__ import annotations

import hashlib
import io
import ipaddress
import os
import socket
import ssl
import tarfile
import textwrap
import time
import urllib.request

from errors import ServiceError, ValidationError
from infra.shell import ShellRunner
from infra.storage import JsonStorage
from infra.systemd import SystemdManager
from models.settings import AppSettings
from paths import ProjectPaths
from services.web_proxy_service import WebProxyService


class HttpsService:
    """An isolated Caddy installation with automatic certificate renewal."""

    CADDY_VERSION = "2.11.7"
    RELEASE_URL = "https://github.com/caddyserver/caddy/releases/download"

    def __init__(self, shell: ShellRunner, systemd: SystemdManager, storage: JsonStorage, paths: ProjectPaths) -> None:
        self.shell = shell
        self.systemd = systemd
        self.storage = storage
        self.paths = paths

    def is_installed(self) -> bool:
        return self.paths.web_service_file.exists()

    def validate_dns(self, settings: AppSettings) -> None:
        if not settings.web_enabled or settings.web_frontend != "caddy":
            return
        try:
            addresses = {ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(
                settings.web_domain, 443, type=socket.SOCK_STREAM,
            )}
        except OSError as exc:
            raise ValidationError("web_dns_unresolved") from exc
        if ipaddress.ip_address(settings.web_public_ip) not in addresses:
            raise ValidationError("web_dns_mismatch")

    @staticmethod
    def check_ports_available() -> None:
        for port in (80, 443):
            for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
                try:
                    with socket.socket(family, socket.SOCK_STREAM) as sock:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        if family == socket.AF_INET6:
                            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                        sock.bind((address, port))
                except OSError as exc:
                    # IPv6 may be disabled on a supported IPv4 server.
                    if family == socket.AF_INET6 and exc.errno in {97, 99, 49, 47}:
                        continue
                    raise ServiceError(f"web_port_in_use:{port}") from exc

    def install_binary(self) -> None:
        if self.paths.caddy_binary.exists():
            return
        machine = os.uname().machine.lower()
        arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
        if not arch:
            raise ServiceError(f"unsupported architecture for telemt release: {machine}")
        asset = f"caddy_{self.CADDY_VERSION}_linux_{arch}.tar.gz"
        release = f"{self.RELEASE_URL}/v{self.CADDY_VERSION}"
        with urllib.request.urlopen(f"{release}/{asset}", timeout=60) as response:
            archive_data = response.read()
        with urllib.request.urlopen(f"{release}/caddy_{self.CADDY_VERSION}_checksums.txt", timeout=30) as response:
            checksum_lines = response.read().decode("utf-8").splitlines()
        expected = next((line.split()[0] for line in checksum_lines
                         if len(line.split()) == 2 and line.split()[1].lstrip("*") == asset), "")
        digest = hashlib.sha512 if len(expected) == 128 else hashlib.sha256
        if not expected or digest(archive_data).hexdigest() != expected.lower():
            raise ServiceError("web_caddy_checksum_failed")
        with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as archive:
            member = next((item for item in archive.getmembers() if item.isfile() and item.name == "caddy"), None)
            if member is None:
                raise ServiceError("web_caddy_binary_missing")
            handle = archive.extractfile(member)
            if handle is None:
                raise ServiceError("web_caddy_binary_missing")
            self.storage.save_bytes(self.paths.caddy_binary, handle.read())
        self.paths.caddy_binary.chmod(0o755)

    def render_unit(self) -> str:
        return textwrap.dedent(f"""\
            [Unit]
            Description=Telegram WEB HTTPS managed by mtp-manager
            After=network-online.target telemt.service
            Wants=network-online.target

            [Service]
            Type=simple
            ExecStart={self.paths.caddy_binary} run --config {self.paths.caddy_config_file} --adapter caddyfile
            Environment=XDG_DATA_HOME={self.paths.caddy_data_dir}
            Environment=XDG_CONFIG_HOME={self.paths.caddy_data_dir / 'config'}
            Restart=on-failure
            RestartSec=3
            NoNewPrivileges=true
            ProtectSystem=full
            ProtectHome=true
            PrivateTmp=true
            LimitNOFILE=65535

            [Install]
            WantedBy=multi-user.target
            """)

    def configure(self, settings: AppSettings) -> None:
        settings.validate()
        config = WebProxyService.render_caddy(settings).replace(
            "# Example only. Caddy obtains and renews the public TLS certificate.",
            "# Managed by mtp-manager. Certificates are obtained and renewed automatically.",
        ).replace("{\n    servers {", "{\n    admin off\n    servers {", 1)
        # Validate a candidate before replacing the live config.
        candidate = self.paths.caddy_config_file.with_suffix(".candidate")
        self.storage.save_text(candidate, config)
        try:
            self.shell.run([str(self.paths.caddy_binary), "validate", "--config", str(candidate), "--adapter", "caddyfile"])
            os.replace(candidate, self.paths.caddy_config_file)
        finally:
            candidate.unlink(missing_ok=True)
        self.paths.caddy_data_dir.mkdir(parents=True, exist_ok=True)
        self.storage.save_text(self.paths.web_service_file, self.render_unit())
        self.systemd.daemon_reload()
        self.systemd.enable(self.paths.web_service_file.name, start=False)

    def stop(self) -> None:
        if self.is_installed():
            self.systemd.stop(self.paths.web_service_file.name)

    def deactivate(self) -> None:
        if self.is_installed():
            self.systemd.disable(self.paths.web_service_file.name)
        self.paths.web_state_file.unlink(missing_ok=True)

    def activate(self, settings: AppSettings, *, wait: bool = True) -> None:
        if not settings.web_enabled or settings.web_frontend != "caddy":
            self.deactivate()
            return
        self.configure(settings)
        self.systemd.restart(self.paths.web_service_file.name)
        if wait:
            self.wait_ready(settings)

    @staticmethod
    def probe(settings: AppSettings) -> None:
        with socket.create_connection(("127.0.0.1", settings.web_port), timeout=2):
            pass
        context = ssl.create_default_context()
        with socket.create_connection(("127.0.0.1", 443), timeout=2) as sock:
            with context.wrap_socket(sock, server_hostname=settings.web_domain):
                pass

    def wait_ready(self, settings: AppSettings, *, timeout: float = 90) -> None:
        self.storage.save_json(self.paths.web_state_file, {"endpoint": settings.web_endpoint, "status": "pending"})
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.probe(settings)
                self.storage.save_json(self.paths.web_state_file, {"endpoint": settings.web_endpoint, "status": "ready"})
                return
            except (OSError, ssl.SSLError):
                if self.systemd.is_active(self.paths.web_service_file.name) == "failed":
                    raise ServiceError("web_https_failed")
                if time.monotonic() >= deadline:
                    raise ServiceError("web_https_pending")
                time.sleep(1)

    def state(self, settings: AppSettings) -> str:
        if not settings.web_enabled:
            return "disabled"
        if settings.web_frontend == "external":
            return "web_external"
        if not self.is_installed():
            return "not-installed"
        active = self.systemd.is_active(self.paths.web_service_file.name)
        if active != "active":
            return active
        state = self.storage.load_json(self.paths.web_state_file, {})
        if state.get("endpoint") == settings.web_endpoint and state.get("status") == "ready":
            return "web_https_ready"
        return "web_https_waiting"

    def logs(self) -> str:
        return self.systemd.logs(self.paths.web_service_file.name)
