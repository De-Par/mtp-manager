from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ExportLinkSet:
    raw_secret: str
    padded_secret: str
    fake_tls_secret: str | None
    tg_raw: str | None
    tg_padded: str | None
    tg_fake_tls: str | None
    tme_raw: str | None
    tme_padded: str | None
    tme_fake_tls: str | None
    tg_web_raw: str | None = None
    tg_web_padded: str | None = None


@dataclass(frozen=True, slots=True)
class ExportBundle:
    host: str
    port: int
    user: str
    secret_id: int
    note: str
    endpoint: str
    links: ExportLinkSet
    labels: dict[str, str] = field(default_factory=dict)
    web_endpoint: str | None = None
