from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


class JsonStorage:
    def ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def load_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def save_json(self, path: Path, payload: dict[str, Any]) -> None:
        self.save_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def save_text(self, path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as handle:
            handle.write(body)
            tmp_path = Path(handle.name)
        os.replace(tmp_path, path)

    def save_bytes(self, path: Path, body: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(path.parent)) as handle:
            handle.write(body)
            tmp_path = Path(handle.name)
        os.replace(tmp_path, path)
