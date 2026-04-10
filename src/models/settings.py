from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Literal

from errors import ValidationError

PORT_MIN = 1
PORT_MAX = 65535
SourceMode = Literal["fresh", "reuse", "update", "rebuild"]
DOMAIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
AD_TAG_RE = re.compile(r"^[0-9A-Fa-f]{32}$")
REF_RE = re.compile(r"^[^\s]+$")
SOURCE_MODES = {"fresh", "reuse", "update", "rebuild"}


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
        )
        settings.validate()
        return settings
