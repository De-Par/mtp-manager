from __future__ import annotations

import shutil

from infra.shell import ShellRunner
from paths import ProjectPaths


class SourceService:
    REPO_URL = "https://github.com/TelegramMessenger/MTProxy"

    def __init__(self, shell: ShellRunner, paths: ProjectPaths) -> None:
        self.shell = shell
        self.paths = paths

    def clone_or_update(self, mode: str) -> None:
        if mode == "fresh" and self.paths.mt_dir.exists():
            shutil.rmtree(self.paths.mt_dir)
        if (self.paths.mt_dir / ".git").exists():
            if mode in {"update", "rebuild"}:
                self.shell.run(["git", "-C", str(self.paths.mt_dir), "fetch", "--all", "--tags"])
                if mode == "update":
                    self.shell.run(["git", "-C", str(self.paths.mt_dir), "pull", "--ff-only"])
        elif not self.paths.mt_dir.exists():
            self.shell.run(["git", "clone", self.REPO_URL, str(self.paths.mt_dir)])

    def build(self) -> None:
        self.shell.run(["make", "clean"], cwd=self.paths.mt_dir)
        self.shell.run(["make", "-j1"], cwd=self.paths.mt_dir)
