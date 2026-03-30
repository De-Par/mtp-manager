from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from errors import ShellError


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class ShellRunner:
    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> CommandResult:
        if self.dry_run:
            return CommandResult(list(args), 0, "", "")
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
        )
        result = CommandResult(list(args), completed.returncode, completed.stdout or "", completed.stderr or "")
        if check and completed.returncode != 0:
            raise ShellError(
                f"command failed: {' '.join(args)}",
                details={"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode},
            )
        return result
