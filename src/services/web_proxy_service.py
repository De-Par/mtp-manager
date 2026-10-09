from __future__ import annotations

from pathlib import Path
import textwrap

from errors import ValidationError
from infra.storage import JsonStorage
from models.settings import AppSettings
from paths import ProjectPaths


class WebProxyService:
    """Prepare the decoy and examples for a local TLS terminator."""

    def __init__(self, storage: JsonStorage, paths: ProjectPaths) -> None:
        self.storage = storage
        self.paths = paths

    def decoy_directory(self, settings: AppSettings) -> Path:
        return Path(settings.web_decoy_dir) if settings.web_decoy_dir else self.paths.web_decoy_dir

    def validate_decoy(self, settings: AppSettings) -> None:
        if settings.web_enabled and settings.web_decoy_dir:
            directory = self.decoy_directory(settings)
            index = directory / "index.html"
            if not directory.is_dir() or directory.is_symlink() or not index.is_file() or index.is_symlink():
                raise ValidationError("web_decoy_dir must be a real directory containing index.html")

    def prepare(self, settings: AppSettings) -> None:
        settings.validate()
        if not settings.web_enabled:
            return
        directory = self.decoy_directory(settings)
        self.validate_decoy(settings)
        if not settings.web_decoy_dir:
            directory.mkdir(parents=True, exist_ok=True)
            index = directory / "index.html"
            if not index.exists():
                self.storage.save_text(index, '<!doctype html><html lang="en"><meta charset="utf-8">'
                                       '<title>Welcome</title><h1>Welcome</h1><p>Website is online.</p></html>\n')
        self.storage.save_text(self.paths.web_nginx_file, self.render_nginx(settings))
        self.storage.save_text(self.paths.web_caddy_file, self.render_caddy(settings))

    @staticmethod
    def render_nginx(settings: AppSettings) -> str:
        settings.validate()
        # Forward both exact no-slash requests and the entire slash-terminated
        # subtree, preserving the URI so Telemt decides the decoy behavior.
        locations = ["/"] if not settings.web_base_path else [
            f"= /{settings.web_base_path}", f"^~ /{settings.web_base_path}/",
        ]
        body = textwrap.dedent(f"""\
            # Example only. Install in NGINX's http context after obtaining a certificate.
            # Do not log carrier credentials. The configured carrier is HTTPS.
            server {{
                listen 443 ssl;
                server_name {settings.web_domain};
                access_log off;
                ssl_certificate /etc/letsencrypt/live/{settings.web_domain}/fullchain.pem;
                ssl_certificate_key /etc/letsencrypt/live/{settings.web_domain}/privkey.pem;
                client_max_body_size 2m;
                client_body_timeout 65s;
                send_timeout 65s;
            """)
        for location in locations:
            body += textwrap.indent(textwrap.dedent(f"""\
                location {location} {{
                    proxy_pass http://127.0.0.1:{settings.web_port};
                    proxy_http_version 1.1;
                    proxy_set_header Host $host;
                    proxy_set_header X-Forwarded-For $remote_addr;
                    proxy_set_header Connection "";
                    proxy_connect_timeout 5s;
                    proxy_send_timeout 65s;
                    proxy_read_timeout 65s;
                    proxy_request_buffering off;
                    proxy_buffering off;
                    proxy_next_upstream off;
                }}
                """), "    ")
        if settings.web_base_path:
            body += "    location / { return 404; }\n"
        return body + "}\n"

    @staticmethod
    def render_caddy(settings: AppSettings) -> str:
        settings.validate()
        proxy = textwrap.dedent(f"""\
            reverse_proxy 127.0.0.1:{settings.web_port} {{
                header_up X-Forwarded-For {{remote_host}}
                flush_interval -1
            }}
            """)
        if settings.web_base_path:
            proxy = (f"@web path /{settings.web_base_path} /{settings.web_base_path}/*\n"
                     "handle @web {\n" + textwrap.indent(proxy, "    ") + "}\n"
                     "handle {\n    respond 404\n}\n")
        return ("# Example only. Caddy obtains and renews the public TLS certificate.\n"
                "{\n    servers {\n        protocols h1 h2\n    }\n}\n\n"
                f"{settings.web_domain} {{\n" + textwrap.indent(proxy, "    ") + "}\n")
