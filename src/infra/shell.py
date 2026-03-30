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
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> CommandResult:
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
