from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ExportLinkSet:
    raw_secret: str
    padded_secret: str
    fake_tls_secret: str | None
    tg_raw: str
    tg_padded: str
    tg_fake_tls: str | None
    tme_raw: str
    tme_padded: str
    tme_fake_tls: str | None


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
