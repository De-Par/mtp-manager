from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SettingsFormData:
    mt_port: int
    stats_port: int
    workers: int
    fake_tls_domain: str
    ad_tag: str
    ui_lang: str
