from pathlib import Path


def supports_web(binary: Path) -> bool:
    """Check the WEB link formatter embedded in current Telemt binaries.

    Old Telemt versions may silently ignore WEB TOML fields. Checking a version
    alone is insufficient because releases and source revisions can share it.
    """
    marker = b"tg://webproxy?server="
    tail = b""
    with binary.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            data = tail + chunk
            if marker in data:
                return True
            tail = data[-len(marker):]
    return False
