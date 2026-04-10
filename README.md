<h1 align="center">mtp-manager</h1>

<p align="center">
  Minimal terminal UI for managing
  <a href="https://github.com/telemt/telemt">telemt</a>
  on Debian, Ubuntu, Fedora, and Arch Linux
</p>

<p align="center">
  <a href="https://pypi.org/project/mtp-manager/">
    <img src="https://img.shields.io/pypi/v/mtp-manager?style=flat-square&label=PyPI&color=7C3AED" alt="PyPI">
  </a>
  <a href="https://docs.python.org/3/">
    <img src="https://img.shields.io/badge/Python-3.11%2B-2563EB?style=flat-square&logoColor=white" alt="Python 3.11+">
  </a>
  <a href="https://textual.textualize.io/">
    <img src="https://img.shields.io/badge/Textual-TUI-16A34A?style=flat-square&logoColor=white" alt="Textual TUI">
  </a>
  <a href="https://github.com/telemt/telemt">
    <img src="https://img.shields.io/badge/Backend-telemt-DC2626?style=flat-square&logoColor=white" alt="telemt backend">
  </a>
</p>

<p align="center">
  <a href="https://ubuntu.com/server">
    <img src="https://img.shields.io/badge/Platform-Debian%20%7C%20Ubuntu%20%7C%20Fedora%20%7C%20Arch-D97706?style=flat-square&logoColor=white" alt="Debian, Ubuntu, Fedora, or Arch Linux">
  </a>
</p>

<p align="center">
  <a href="src/i18n/en.py">
    <img src="https://img.shields.io/badge/Language-English-175569?style=flat-square&logoColor=white" alt="English UI">
  </a>
  <a href="src/i18n/ru.py">
    <img src="https://img.shields.io/badge/Language-Русский-DB2777?style=flat-square&logoColor=white" alt="Russian UI">
  </a>
  <a href="src/i18n/zh.py">
    <img src="https://img.shields.io/badge/Language-中文-0891B2?style=flat-square&logoColor=white" alt="Chinese UI">
  </a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/De-Par/mtp-manager/main/assets/demo.png" alt="mtp-manager screenshot" width="80%">
</p>

## Overview

`mtp-manager` is a lightweight TUI for installing, configuring, and operating a `telemt`-based MTProto proxy with Fake TLS support. It is designed for small VPS setups where a compact workflow matters more than a large control panel.

## Highlights

- install and update `telemt`
- install a specific tag or commit
- manage users and secrets
- export `raw`, `dd`, and `ee` links
- inspect service status and logs
- run cleanup tasks for logs, cache, and runtime artifacts
- switch the interface between English, Russian, and Chinese

## Request Flow

The diagram below shows the high-level path of an MTProto message when `telemt` is used as the proxy layer with Fake TLS enabled.

<p align="center">
  <img src="https://raw.githubusercontent.com/De-Par/mtp-manager/main/assets/diagram.png" alt="mtproto arch">
</p>

## Installation

### From PyPI

Install the latest published version from PyPI:

```bash
python3 -m pip install mtp-manager
```

Run the application:

```bash
mtp-manager
```

> `mtp-manager` performs system-level operations such as service management, firewall updates, and cleanup tasks, so it is typically expected to run with root privileges.

### From source

Clone the repository and use the bootstrap script:

```bash
source setup.sh
mtp-manager
```

`setup.sh` is meant to be sourced from `bash` or `zsh`. It prepares `.venv`, installs the project in editable mode, validates the entrypoint, and activates the environment in the current shell.

## Requirements

- Python `3.11+`
- Debian, Ubuntu, Fedora, or Arch Linux
- `systemd`
- root privileges for install, service, firewall, and cleanup operations

## Project Layout

| Path | Purpose |
| --- | --- |
| `src/app.py` | CLI entrypoint and internal service commands |
| `src/bootstrap.py` | Dependency wiring and startup migration glue |
| `src/controller.py` | Application actions used by the TUI |
| `src/infra/` | shell, locale, storage, firewall, public IP, `systemd` |
| `src/models/` | typed domain models |
| `src/services/` | install, runtime, diagnostics, cleanup, inventory |
| `src/ui/backend.py` | UI backend abstraction used by the app entrypoint |
| `src/ui/textual_app.py` | main TUI orchestration |
| `src/ui/modals.py` | modal screens and shared popup UI |
| `src/ui/dashboard.py` | dashboard rendering and host metrics |
| `src/ui/actions.py` | action definitions and menu helpers |
| `src/ui/lists.py` | sections, users, and secrets list helpers |
| `src/i18n/` | English, Russian, and Chinese catalogs |

## Managed Paths

| Path | Purpose |
| --- | --- |
| `/etc/mtp-manager` | managed config directory |
| `/var/lib/mtp-manager` | app data |
| `/opt/telemt` | installed telemt binary |
| `/etc/systemd/system/telemt.service` | main service unit |
| `/etc/systemd/system/telemt-config-refresh.*` | config refresh service and timer |
| `/etc/systemd/system/mtp-manager-cleanup.*` | cleanup service and timer |

## Notes

- shell execution is routed through the infra layer
- generated files are written atomically
- managed `systemd` units invoke the installed `mtp-manager` entrypoint
- migration logic for older `mtproxy` layouts is included
