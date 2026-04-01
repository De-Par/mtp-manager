from __future__ import annotations

import shutil

from infra.shell import ShellRunner
from paths import ProjectPaths


class SourceService:
    REPO_URL = "https://github.com/TelegramMessenger/MTProxy"
    PID_ASSERT = "    assert (!(p & 0xffff0000));\n    PID.pid = p;\n"
    PID_PATCH = "    PID.pid = (unsigned short) (p & 0xffff);\n"

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
        self.apply_local_patches()

    def apply_local_patches(self) -> None:
        pid_file = self.paths.mt_dir / "common" / "pid.c"
        if not pid_file.exists():
            return
        source = pid_file.read_text(encoding="utf-8")
        if self.PID_PATCH in source:
            return
        if self.PID_ASSERT not in source:
            return
        pid_file.write_text(source.replace(self.PID_ASSERT, self.PID_PATCH), encoding="utf-8")

    def build(self) -> None:
        self.apply_local_patches()
        self.shell.run(["make", "clean"], cwd=self.paths.mt_dir)
        self.shell.run(["make", "-j1"], cwd=self.paths.mt_dir)
