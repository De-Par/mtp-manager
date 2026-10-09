"""Exercise the sourced installer without package downloads or host changes."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (PROJECT_ROOT / "setup.sh").read_text()
SHELLS = tuple(shell for name in ("bash", "zsh") if (shell := shutil.which(name)))

FAKE_PYTHON = r'''
import json
import os
from pathlib import Path
import shlex
import sys

args = sys.argv[1:]
body = sys.stdin.read() if args == ["-"] else ""
if args[:2] == ["-m", "venv"]:
    stage = "venv"
elif args[:2] == ["-m", "pip"]:
    stage = "upgrade" if "--upgrade" in args else "install"
elif args == ["-"]:
    stage = "verify" if "importlib.metadata" in body else "version"
else:
    stage = "environment"
with open(os.environ["MTP_BOOTSTRAP_CALLS"], "a") as stream:
    stream.write(json.dumps({"stage": stage, "args": args, "body": body}) + "\n")
if stage == os.environ.get("MTP_BOOTSTRAP_FAIL"):
    print("simulated " + stage + " failure", file=sys.stderr)
    raise SystemExit(42)
venv = Path(os.environ["MTP_BOOTSTRAP_VENV"])
if stage == "venv":
    bin_dir = venv / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    interpreter = bin_dir / "python"
    if interpreter.is_symlink() or interpreter.exists():
        interpreter.unlink()
    interpreter.symlink_to(Path(sys.argv[0]).resolve())
    (bin_dir / "activate").write_text(
        "VIRTUAL_ENV=" + shlex.quote(str(venv)) + "\n"
        'export VIRTUAL_ENV\nPATH="$VIRTUAL_ENV/bin:$PATH"\nexport PATH\n'
    )
if stage == "install" and not os.environ.get("MTP_BOOTSTRAP_OMIT_COMMAND"):
    command = venv / "bin/mtp-manager"
    command.write_text("#!/bin/sh\nexit 0\n")
    command.chmod(0o755)
if stage == "verify" and os.environ.get("MTP_BOOTSTRAP_FAIL") == "activation":
    (venv / "bin/activate").unlink()
'''

SOURCE = r'''
set -eu
set -o pipefail
before_options="$(set -o)"
if source "$MTP_BOOTSTRAP_SCRIPT"; then
  setup_result=0
else
  setup_result=$?
fi
after_options="$(set -o)"
if [ "$before_options" != "$after_options" ]; then
  printf 'caller shell options changed\n' >&2
  exit 99
fi
printf 'CALLER_DIR=%s\nACTIVE_ENV=%s\n' "$PWD" "${VIRTUAL_ENV:-}"
if [ "$setup_result" -eq 0 ]; then command -v mtp-manager; fi
exit "$setup_result"
'''


class BootstrapTests(unittest.TestCase):
    def run_setup(self, shell, *, fail="", protected_cache=False,
                  partial=False, missing_python=False, omit_command=False,
                  package_failure=False, relative_venv=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            project = root / "project with spaces"
            project.mkdir()
            script = project / "setup.sh"
            script.write_text(SCRIPT)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            python = bin_dir / "python"
            python.write_text(f"#!{sys.executable}\n" + FAKE_PYTHON)
            python.chmod(0o755)
            venv = project / ".venv"
            if partial:
                venv.mkdir()
                (venv / "keep.txt").write_text("do not delete existing contents")
            cache = project / "src/__pycache__"
            cache.mkdir(parents=True)
            bytecode = cache / "module.pyc"
            bytecode.write_bytes(b"old bytecode")
            if protected_cache:
                cache.chmod(0o555)
            calls = root / "calls.jsonl"
            env = dict(os.environ)
            env.pop("VIRTUAL_ENV", None)
            env.update(
                PYTHON_BIN=str(root / "missing-python") if missing_python else str(python),
                VENV_DIR=".venv" if relative_venv else str(venv),
                INSTALL_SYSTEM_DEPS="0",
                MTP_BOOTSTRAP_SCRIPT=str(script),
                MTP_BOOTSTRAP_VENV=str(venv),
                MTP_BOOTSTRAP_CALLS=str(calls),
                MTP_BOOTSTRAP_FAIL=fail,
                MTP_BOOTSTRAP_OMIT_COMMAND="1" if omit_command else "",
            )
            if package_failure:
                # Stub the OS boundary to exercise Debian on any development host.
                script.write_text(SCRIPT.rsplit('\nmain "$@"', 1)[0] + '''
detect_distro_family() { printf 'debian\\n'; }
main "$@" || return
''')
                for name, content in (
                    ("id", "printf '0\\n'\n"),
                    ("apt-get", "printf 'simulated apt failure\\n' >&2\nexit 19\n"),
                ):
                    command = bin_dir / name
                    command.write_text("#!/bin/sh\n" + content)
                    command.chmod(0o755)
                env["PATH"] = f"{bin_dir}:{env['PATH']}"
                env["INSTALL_SYSTEM_DEPS"] = "1"
            try:
                result = subprocess.run(
                    [shell, "-c", SOURCE], cwd=root, env=env,
                    capture_output=True, text=True, timeout=30,
                )
                history = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
                state = {
                    "root": root, "venv": venv, "cache_remains": bytecode.exists(),
                    "old_file_remains": (venv / "keep.txt").exists(),
                }
                return result, history, state
            finally:
                if cache.exists():
                    cache.chmod(0o755)

    def assert_failed(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(result.returncode, 99, result.stderr)
        self.assertIn("[setup] error:", result.stderr)
        self.assertNotIn("Virtual environment is active", result.stdout)
        self.assertIn("ACTIVE_ENV=\n", result.stdout)

    def test_success_activates_in_callers_shell_and_preserves_options_and_directory(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, calls, state = self.run_setup(shell, relative_venv=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"ACTIVE_ENV={state['venv']}\n", result.stdout)
                self.assertIn(f"CALLER_DIR={state['root']}\n", result.stdout)
                self.assertIn(f"{state['venv']}/bin/mtp-manager\n", result.stdout)
                self.assertEqual([call["stage"] for call in calls],
                                 ["version", "venv", "upgrade", "install", "verify"])
                self.assertNotIn("build_container()", calls[-1]["body"])

    @unittest.skipIf(os.geteuid() == 0, "root can remove the protected fixture")
    def test_unwritable_cache_does_not_block_installation(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, calls, state = self.run_setup(shell, protected_cache=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(state["cache_remains"])
                self.assertIn("continuing installation", result.stderr)
                self.assertEqual(calls[-1]["stage"], "verify")

    def test_incomplete_environment_is_repaired_without_deleting_contents(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, _, state = self.run_setup(shell, partial=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Repairing incomplete virtual environment", result.stdout)
                self.assertTrue(state["old_file_remains"])

    def test_missing_python_stops_before_environment_creation(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, calls, _ = self.run_setup(shell, missing_python=True)
                self.assert_failed(result)
                self.assertEqual(calls, [])

    def test_required_stage_failure_stops_without_activation_even_inside_if(self):
        stages = ["version", "venv", "upgrade", "install", "verify"]
        for shell in SHELLS:
            for stage in stages:
                with self.subTest(shell=shell, stage=stage):
                    result, calls, _ = self.run_setup(shell, fail=stage)
                    self.assert_failed(result)
                    self.assertEqual([call["stage"] for call in calls],
                                     stages[:stages.index(stage) + 1])

    def test_missing_installed_command_is_reported_before_import(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, calls, _ = self.run_setup(shell, omit_command=True)
                self.assert_failed(result)
                self.assertIn("Installed command not found", result.stderr)
                self.assertEqual(calls[-1]["stage"], "install")

    def test_missing_activation_script_cannot_report_success(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, _, _ = self.run_setup(shell, fail="activation")
                self.assert_failed(result)
                self.assertIn("activation script not found", result.stderr)

    def test_system_package_failure_stops_before_python_or_pip(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, calls, _ = self.run_setup(shell, package_failure=True)
                self.assert_failed(result)
                self.assertIn("Could not install system packages", result.stderr)
                self.assertEqual(calls, [])

    def test_direct_execution_requires_source_in_bash_and_zsh(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = subprocess.run([shell, str(PROJECT_ROOT / "setup.sh")],
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("run this script via source", result.stderr)
                self.assertNotIn("Removing build", result.stdout)


if __name__ == "__main__":
    unittest.main()
