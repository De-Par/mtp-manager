from __future__ import annotations

from dataclasses import asdict, dataclass
import ipaddress
from pathlib import Path
import re
from typing import Literal

from errors import ValidationError

PORT_MIN = 1
PORT_MAX = 65535
SourceMode = Literal["fresh", "reuse", "update", "rebuild"]
ProxyMode = Literal["mtproto", "web", "both"]
DOMAIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
AD_TAG_RE = re.compile(r"^[0-9A-Fa-f]{32}$")
REF_RE = re.compile(r"^[^\s]+$")
SOURCE_MODES = {"fresh", "reuse", "update", "rebuild"}
WEB_BASE_PATH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*(?:/[A-Za-z0-9][A-Za-z0-9_-]*)*")


@dataclass(slots=True)
class AppSettings:
    mt_port: int = 443
    stats_port: int = 8888
    workers: int = 1
    fake_tls_domain: str = ""
    ad_tag: str = ""
    telemt_ref: str = ""
    ui_lang: str = "en"
    source_mode: SourceMode = "fresh"
    proxy_mode: ProxyMode = "mtproto"
    web_domain: str = ""
    web_public_ip: str = ""
    web_port: int = 18080
    web_base_path: str = ""
    web_decoy_dir: str = ""
    web_frontend: Literal["caddy", "external"] = "caddy"

    @property
    def mtproto_enabled(self) -> bool:
        return self.proxy_mode in {"mtproto", "both"}

    @property
    def web_enabled(self) -> bool:
        return self.proxy_mode in {"web", "both"}

    @property
    def public_ports(self) -> set[int]:
        ports = {self.mt_port} if self.mtproto_enabled else set()
        if self.web_enabled:
            ports.add(443)
            if self.web_frontend == "caddy":
                ports.add(80)
        return ports

    @property
    def web_endpoint(self) -> str:
        base = f"{self.web_base_path}/" if self.web_base_path else ""
        return f"https://{self.web_domain}/{base}"

    @property
    def web_public_addr(self) -> str:
        ip = ipaddress.ip_address(self.web_public_ip)
        return f"[{ip}]:443" if ip.version == 6 else f"{ip}:443"

    def validate(self) -> None:
        for field_name in ("mt_port", "stats_port"):
            value = getattr(self, field_name)
            if not PORT_MIN <= value <= PORT_MAX:
                raise ValidationError(f"{field_name} must be in range {PORT_MIN}..{PORT_MAX}")
        if self.workers < 0:
            raise ValidationError("workers must be >= 0")
        if self.ui_lang not in {"ru", "en", "zh"}:
            raise ValidationError("ui_lang must be 'ru', 'en', or 'zh'")
        if self.fake_tls_domain and not DOMAIN_RE.fullmatch(self.fake_tls_domain):
            raise ValidationError("fake_tls_domain must be a valid domain name")
        if self.ad_tag and not AD_TAG_RE.fullmatch(self.ad_tag):
            raise ValidationError("ad_tag must be a 32-character hexadecimal string")
        if self.telemt_ref and not REF_RE.fullmatch(self.telemt_ref):
            raise ValidationError("telemt_ref must not contain whitespace")
        if self.source_mode not in SOURCE_MODES:
            raise ValidationError("source_mode is invalid")
        if self.proxy_mode not in {"mtproto", "web", "both"}:
            raise ValidationError("proxy_mode is invalid")
        if not self.web_enabled:
            return
        if self.web_frontend not in {"caddy", "external"}:
            raise ValidationError("web_frontend is invalid")
        if (not DOMAIN_RE.fullmatch(self.web_domain) or len(self.web_domain) > 253
                or self.web_domain != self.web_domain.lower() or self.web_domain.rsplit(".", 1)[-1].isdigit()):
            raise ValidationError("web_domain must be a lowercase domain name")
        try:
            ip = ipaddress.ip_address(self.web_public_ip)
        except ValueError as exc:
            raise ValidationError("web_public_ip must be a public IP address") from exc
        if not ip.is_global or ip.is_multicast or "%" in self.web_public_ip:
            raise ValidationError("web_public_ip must be a public IP address")
        if not PORT_MIN <= self.web_port <= PORT_MAX:
            raise ValidationError(f"web_port must be in range {PORT_MIN}..{PORT_MAX}")
        reserved = {80, 443} if self.web_frontend == "caddy" else {443}
        if (self.web_port in reserved | {self.stats_port} or self.stats_port in reserved
                or (self.mtproto_enabled and self.mt_port in reserved | {self.stats_port, self.web_port})):
            raise ValidationError("WEB ports conflict; use distinct MTProto, API, WEB listener ports and reserve 443 for HTTPS")
        if self.web_base_path and (len(self.web_base_path) > 128 or not WEB_BASE_PATH_RE.fullmatch(self.web_base_path)):
            raise ValidationError("web_base_path must contain slash-separated ASCII segments without leading or trailing slash (max 128 characters)")
        if self.web_decoy_dir and (not Path(self.web_decoy_dir).is_absolute() or any(ord(char) < 32 for char in self.web_decoy_dir)):
            raise ValidationError("web_decoy_dir must be an absolute directory path")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AppSettings":
        settings = cls(
            mt_port=int(payload.get("mt_port", 443)),
            stats_port=int(payload.get("stats_port", 8888)),
            workers=int(payload.get("workers", 1)),
            fake_tls_domain=str(payload.get("fake_tls_domain", "")),
            ad_tag=str(payload.get("ad_tag", "")),
            telemt_ref=str(payload.get("telemt_ref", "")),
            ui_lang=str(payload.get("ui_lang", "en")),
            source_mode=str(payload.get("source_mode", "fresh")),  # type: ignore[arg-type]
            proxy_mode=str(payload.get("proxy_mode", "mtproto")),  # type: ignore[arg-type]
            web_domain=str(payload.get("web_domain", "")),
            web_public_ip=str(payload.get("web_public_ip", "")),
            web_port=int(payload.get("web_port", 18080)),
            web_base_path=str(payload.get("web_base_path", "")),
            web_decoy_dir=str(payload.get("web_decoy_dir", "")),
            # Existing WEB settings used external frontend examples.
            web_frontend=str(payload.get("web_frontend", "external" if payload.get("proxy_mode") in {"web", "both"} else "caddy")),  # type: ignore[arg-type]
        )
        settings.validate()
        return settings
