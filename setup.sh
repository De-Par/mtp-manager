#!/usr/bin/env bash

_setup_script_path() {
  if [ -n "${ZSH_VERSION:-}" ]; then
    printf '%s\n' "${(%):-%x}"
    return
  fi
  if [ -n "${BASH_VERSION:-}" ]; then
    printf '%s\n' "${BASH_SOURCE[0]}"
    return
  fi
  printf '%s\n' "$0"
}

if ! (return 0 2>/dev/null); then
  printf '[setup] error: run this script via source, not as an executable\n' >&2
  printf '[setup]   source "%s"\n' "$(_setup_script_path)" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$(_setup_script_path)")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_SYSTEM_DEPS="${INSTALL_SYSTEM_DEPS:-auto}"

log() {
  printf '[setup] %s\n' "$1"
}

warn() {
  printf '[setup] warning: %s\n' "$1" >&2
}

die() {
  printf '[setup] error: %s\n' "$1" >&2
  return 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  if have_cmd sudo; then
    sudo "$@"
    return
  fi
  die "sudo is required to install system packages"
}

clean_artifacts() {
  log "Removing build and cache artifacts"
  find "$ROOT_DIR" \
    \( -path "$ROOT_DIR/.git" -o -path "$VENV_DIR" \) -prune -o \
    \( -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name "*.egg-info" \) -exec rm -rf {} + \)
  rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist"
}

install_system_deps() {
  if [ "$INSTALL_SYSTEM_DEPS" = "0" ] || [ "$INSTALL_SYSTEM_DEPS" = "false" ]; then
    log "Skipping system packages by request"
    return
  fi
  if ! have_cmd apt-get; then
    warn "apt-get not found; skipping system package installation"
    return
  fi
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}" in
      debian|ubuntu) ;;
      *)
        if [ "$INSTALL_SYSTEM_DEPS" = "auto" ]; then
          warn "Unsupported distro for automatic package install: ${ID:-unknown}"
          return
        fi
        ;;
    esac
  fi
  log "Installing system packages"
  run_privileged apt-get update
  run_privileged apt-get install -y \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    libssl-dev \
    zlib1g-dev
}

ensure_python() {
  have_cmd "$PYTHON_BIN" || die "Python interpreter not found: $PYTHON_BIN"
  "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

create_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  else
    log "Using existing virtual environment at $VENV_DIR"
  fi
}

install_python_deps() {
  log "Upgrading packaging tools"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
  log "Installing project in editable mode"
  "$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR"
}

run_smoke_check() {
  log "Running smoke check"
  MTPROXY_MANAGER_STATE_ROOT="$ROOT_DIR/.devstate" "$VENV_DIR/bin/python" "$ROOT_DIR/mtp-manager.py" --console --dry-run >/dev/null
}

activate_venv() {
  if [ ! -f "$VENV_DIR/bin/activate" ]; then
    die "virtual environment activation script not found: $VENV_DIR/bin/activate"
  fi
  # shellcheck disable=SC1090
  . "$VENV_DIR/bin/activate"
  hash -r 2>/dev/null || true
  log "Virtual environment is active: $VENV_DIR"
}

print_source_hint() {
  cat <<EOF

[setup] Done.
[setup] Virtual environment has been activated in the current shell.
[setup] Quick run:
[setup]   python "$ROOT_DIR/mtp-manager.py" --console --dry-run
EOF
}

setup_pipeline() {
  set -euo pipefail
  cd "$ROOT_DIR"
  clean_artifacts
  install_system_deps
  ensure_python
  create_venv
  install_python_deps
  run_smoke_check
}

main() {
  (set -euo pipefail; setup_pipeline "$@")
  activate_venv
  print_source_hint
}

main "$@"
