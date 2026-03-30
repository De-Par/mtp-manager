from __future__ import annotations

from pathlib import Path

from models.export import ExportBundle, ExportLinkSet
from models.secret import SecretRecord, UserRecord
from models.settings import AppSettings


class ExportService:
    @staticmethod
    def padded_secret(raw_secret: str) -> str:
        return f"dd{raw_secret}"

    @staticmethod
    def fake_tls_secret(raw_secret: str, domain: str) -> str:
        return f"ee{raw_secret}{domain.encode('utf-8').hex()}"

    @staticmethod
    def tg_link(host: str, port: int, secret: str) -> str:
        return f"tg://proxy?server={host}&port={port}&secret={secret}"

    @staticmethod
    def tme_link(host: str, port: int, secret: str) -> str:
        return f"https://t.me/proxy?server={host}&port={port}&secret={secret}"

    def build_bundle(self, host: str, settings: AppSettings, user: UserRecord, secret: SecretRecord) -> ExportBundle:
        raw = secret.raw_secret
        padded = self.padded_secret(raw)
        fake = self.fake_tls_secret(raw, settings.fake_tls_domain) if settings.fake_tls_domain else None
        return ExportBundle(
            host=host,
            port=settings.mt_port,
            user=user.name,
            secret_id=secret.id,
            note=secret.note,
            endpoint=f"{host}:{settings.mt_port}",
            links=ExportLinkSet(
                raw_secret=raw,
                padded_secret=padded,
                fake_tls_secret=fake,
                tg_raw=self.tg_link(host, settings.mt_port, raw),
                tg_padded=self.tg_link(host, settings.mt_port, padded),
                tg_fake_tls=self.tg_link(host, settings.mt_port, fake) if fake else None,
                tme_raw=self.tme_link(host, settings.mt_port, raw),
                tme_padded=self.tme_link(host, settings.mt_port, padded),
                tme_fake_tls=self.tme_link(host, settings.mt_port, fake) if fake else None,
            ),
        )

    def render_bundles(self, bundles: list[ExportBundle]) -> str:
        lines: list[str] = []
        for bundle in bundles:
            lines.extend(
                [
                    f"User: {bundle.user} / Secret ID: {bundle.secret_id}",
                    f"Endpoint: {bundle.endpoint}",
                    f"Raw: {bundle.links.raw_secret}",
                    f"DD: {bundle.links.padded_secret}",
                    f"EE: {bundle.links.fake_tls_secret or 'disabled'}",
                    f"tg raw: {bundle.links.tg_raw}",
                    f"t.me raw: {bundle.links.tme_raw}",
                    f"tg dd: {bundle.links.tg_padded}",
                    f"t.me dd: {bundle.links.tme_padded}",
                    f"tg ee: {bundle.links.tg_fake_tls or 'disabled'}",
                    f"t.me ee: {bundle.links.tme_fake_tls or 'disabled'}",
                    "",
                ]
            )
        return "\n".join(lines).strip()

    def export_bundles_to_file(self, bundles: list[ExportBundle], path: Path) -> Path:
        body = self.render_bundles(bundles)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body + ("\n" if body else ""), encoding="utf-8")
        return path
