# mtp-manager

`mtp-manager` is a TUI manager for MTProxy on Debian and Ubuntu.

## Quick Start

```bash
source setup.sh
mtp-manager
```

`setup.sh` is meant to be loaded with `source` from `bash` or `zsh`. It cleans local build artifacts, prepares `.venv`, installs the project in editable mode, validates the installed entrypoint, and activates the environment in the current shell.

## What It Does

- installs and updates MTProxy sources
- generates and refreshes runtime configuration
- manages `systemd` units and timers
- manages users and secrets
- exports connection links and secret formats
- shows health, logs, and service diagnostics

## Runtime Requirements

- Python `3.11+`
- Debian or Ubuntu
- `systemd`
- root privileges for install, firewall, locale, cleanup, and service actions

## Layout

- `src/app.py`: CLI entrypoint and internal service commands
- `src/bootstrap.py`: dependency wiring
- `src/controller.py`: application actions for the TUI
- `src/services/`: MTProxy lifecycle services
- `src/infra/`: shell, storage, locale, firewall, `systemd`
- `src/ui/`: `prompt_toolkit` TUI
- `src/models/`: typed domain models
- `src/i18n/`: RU and EN text catalogs

## Managed Paths

- `/etc/mtproxy-manager`
- `/var/lib/mtproxy-manager`
- `/etc/systemd/system/mtproxy.service`
- `/etc/systemd/system/mtproxy-config-update.service`
- `/etc/systemd/system/mtproxy-config-update.timer`
- `/etc/systemd/system/mtproxy-cleanup.service`
- `/etc/systemd/system/mtproxy-cleanup.timer`
- `/opt/MTProxy`

## Notes

- all shell execution goes through the infra layer
- state and generated files are written atomically
- generated `systemd` units launch the installed `mtp-manager` entrypoint
