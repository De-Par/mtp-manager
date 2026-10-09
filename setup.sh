#!/usr/bin/env bash

setup_script_path() {
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

if { [ -n "${BASH_VERSION:-}" ] && ! (return 0 2>/dev/null); } ||
   { [ -n "${ZSH_VERSION:-}" ] && [[ "${ZSH_EVAL_CONTEXT:-}" != *:file ]]; }; then
  printf '[setup] error: run this script via source, not as an executable\n' >&2
  printf '[setup]   source "%s"\n' "$(setup_script_path)" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$(setup_script_path)")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
case "$VENV_DIR" in
  /*) ;;
  *) VENV_DIR="$ROOT_DIR/$VENV_DIR" ;;
esac
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_SYSTEM_DEPS="${INSTALL_SYSTEM_DEPS:-auto}"
DISTRO_FAMILY=""

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

has_command() {
  command -v "$1" >/dev/null 2>&1
}

detect_distro_family() {
  if [ -z "${DISTRO_FAMILY:-}" ] && [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    local distro_id="${ID:-}"
    local distro_like="${ID_LIKE:-}"
    case " $distro_id $distro_like " in
      *" debian "*|*" ubuntu "*) DISTRO_FAMILY="debian" ;;
      *" fedora "*|*" rhel "*|*" rocky "*|*" almalinux "*|*" centos "*) DISTRO_FAMILY="fedora" ;;
      *" arch "*|*" archlinux "*|*" manjaro "*) DISTRO_FAMILY="arch" ;;
      *) DISTRO_FAMILY="unknown" ;;
    esac
  fi
  printf '%s\n' "${DISTRO_FAMILY:-unknown}"
}

run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  if has_command sudo; then
    sudo "$@"
    return
  fi
  die "sudo is required to install system packages"
}

cleanup_project_artifacts() {
  log "Removing build and cache artifacts"
  if ! find "$ROOT_DIR" \
    \( -path "$ROOT_DIR/.git" -o -path "$VENV_DIR" -o -name ".venv" \) -prune -o \
    \( -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name "*.egg-info" \) -exec rm -rf {} + \) 2>/dev/null; then
    warn "Some cache artifacts could not be removed (permissions); continuing installation"
  fi
  if ! rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist" 2>/dev/null; then
    warn "Some build artifacts could not be removed (permissions); continuing installation"
  fi
}

install_system_deps() {
  if [ "$INSTALL_SYSTEM_DEPS" = "0" ] || [ "$INSTALL_SYSTEM_DEPS" = "false" ]; then
    log "Skipping system packages by request"
    return
  fi
  local family
  family="$(detect_distro_family)"
  log "Installing system packages"
  case "$family" in
    debian)
      run_privileged apt-get update || return
      run_privileged apt-get install -y \
        ca-certificates \
        python3 \
        python3-venv
      ;;
    fedora)
      run_privileged dnf install -y \
        ca-certificates \
        python3
      ;;
    arch)
      run_privileged pacman -Sy --noconfirm \
        ca-certificates \
        python
      ;;
    *)
      if [ "$INSTALL_SYSTEM_DEPS" = "auto" ]; then
        warn "Unsupported distro for automatic package install: ${ID:-unknown}"
        return
      fi
      die "Unsupported distro for automatic package install: ${ID:-unknown}"
      ;;
  esac
}

ensure_python() {
  if ! has_command "$PYTHON_BIN"; then
    die "Python interpreter not found: $PYTHON_BIN"
    return 1
  fi
  if ! "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
  then
    die "Python 3.11 or newer is required: $PYTHON_BIN"
    return 1
  fi
}

ensure_venv() {
  if [ -x "$VENV_DIR/bin/python" ] && [ -f "$VENV_DIR/bin/activate" ] &&
     "$VENV_DIR/bin/python" -c 'import pip, sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    log "Using existing virtual environment at $VENV_DIR"
    return
  fi
  if [ -d "$VENV_DIR" ]; then
    log "Repairing incomplete virtual environment at $VENV_DIR"
  else
    log "Creating virtual environment at $VENV_DIR"
  fi
  if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
    die "Could not prepare virtual environment at $VENV_DIR; check directory permissions and the Python venv package"
    return 1
  fi
  if [ ! -x "$VENV_DIR/bin/python" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    die "Virtual environment is incomplete: $VENV_DIR"
    return 1
  fi
}

install_project() {
  log "Upgrading packaging tools"
  if ! PIP_NO_CACHE_DIR=1 "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel; then
    die "Could not install packaging tools; check the pip output above"
    return 1
  fi
  log "Installing project in editable mode"
  if ! PIP_NO_CACHE_DIR=1 "$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR" --no-build-isolation; then
    die "Could not install mtp-manager; check the pip output above"
    return 1
  fi
}

verify_installation() {
  log "Verifying installed entrypoint"
  if [ ! -x "$VENV_DIR/bin/mtp-manager" ]; then
    die "Installed command not found: $VENV_DIR/bin/mtp-manager"
    return 1
  fi
  if ! PYTHONDONTWRITEBYTECODE=1 "$VENV_DIR/bin/python" - <<'PY'
from importlib.metadata import distribution

entrypoint = next(
    entry for entry in distribution("mtp-manager").entry_points
    if entry.group == "console_scripts" and entry.name == "mtp-manager"
)
if not callable(entrypoint.load()):
    raise RuntimeError("mtp-manager entrypoint is not callable")
PY
  then
    die "Could not import the installed mtp-manager entrypoint"
    return 1
  fi
}

activate_venv() {
  if [ ! -f "$VENV_DIR/bin/activate" ]; then
    die "virtual environment activation script not found: $VENV_DIR/bin/activate"
    return 1
  fi
  # shellcheck disable=SC1090
  if ! . "$VENV_DIR/bin/activate"; then
    die "Could not activate virtual environment: $VENV_DIR"
    return 1
  fi
  hash -r 2>/dev/null || true
  log "Virtual environment is active: $VENV_DIR"
}

setup_pipeline() {
  cd "$ROOT_DIR" || return
  cleanup_project_artifacts
  install_system_deps || { die "Could not install system packages"; return 1; }
  ensure_python || return
  ensure_venv || return
  install_project || return
  verify_installation || return
}

main() {
  # Explicit status checks also work when sourced inside an if/&&/|| expression,
  # where bash and zsh disable errexit even in a subshell.
  (setup_pipeline "$@") || return
  activate_venv
}

main "$@" || return
