from __future__ import annotations


def build_fake_tls_secret(raw_secret: str, domain: str) -> str:
    return f"ee{raw_secret}{domain.encode('utf-8').hex()}"
