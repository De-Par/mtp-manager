from __future__ import annotations

from pathlib import Path
import tempfile
import os

from .shell import ShellRunner


class LocaleManager:
    def __init__(self, shell: ShellRunner, target_path: Path = Path("/etc/default/locale")) -> None:
        self.shell = shell
        self.target_path = target_path

    def ensure_c_utf8(self) -> None:
        if self.shell.dry_run:
            return
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(self.target_path.parent), encoding="utf-8") as handle:
            handle.write("LANG=C.UTF-8\nLC_CTYPE=C.UTF-8\n")
            tmp_path = Path(handle.name)
        os.replace(tmp_path, self.target_path)
        self.shell.run(["update-locale", "LANG=C.UTF-8", "LC_CTYPE=C.UTF-8"], check=False)
