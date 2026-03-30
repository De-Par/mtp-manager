# MTProxy Manager

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Debian%20%7C%20Ubuntu-E95420?logo=ubuntu&logoColor=white)
![UI](https://img.shields.io/badge/UI-prompt__toolkit-5A3FC0)
![Init](https://img.shields.io/badge/Init-systemd-000000?logo=systemd&logoColor=white)
![Status](https://img.shields.io/badge/Status-Modular%20Rewrite-1F883D)

Modern MTProxy lifecycle manager for Debian and Ubuntu VPS.

> Keyboard-friendly and mouse-friendly TUI, explicit service layer, clean infra boundaries, and no monolithic wrapper script.

## ✨ Highlights

- 🧱 modular architecture with a thin root entrypoint
- 🖥️ `prompt_toolkit` TUI with automatic console fallback
- 🔐 user and secret inventory with Fake TLS aware export
- ⚙️ setup, rebuild, runtime refresh, cleanup, and `systemd` management
- 🌐 public IP, health, and diagnostics reporting
- 🌍 RU and EN interface support

## 🗂️ Project Layout

```text
MTProto/
├── mtp-manager.py
├── pyproject.toml
├── README.md
└── src/
    ├── app.py
    ├── bootstrap.py
    ├── controller.py
    ├── errors.py
    ├── paths.py
    ├── diagnostics/
    ├── i18n/
    ├── infra/
    ├── models/
    ├── services/
    └── ui/
```

## 🧠 Architecture

| Layer | Responsibility |
| --- | --- |
| `mtp-manager.py` | Thin launcher only |
| `app.py` | Main entrypoint and internal command dispatch |
| `bootstrap.py` | Dependency wiring and backend selection |
| `controller.py` | UI-facing use cases and view orchestration |
| `services/` | Setup, inventory, runtime, exports, diagnostics, cleanup, `systemd` |
| `infra/` | Shell, storage, locale, distro, firewall, public IP, low-level `systemd` |
| `ui/` | `prompt_toolkit` app and console fallback |
| `models/` | Typed domain state |
| `i18n/` | RU and EN text catalog |
| `diagnostics/` | AWS, ports, Fake TLS, and service health checks |

## 🚀 What The Manager Handles

- initial install flow for Debian and Ubuntu
- MTProxy source clone, update, and rebuild
- runtime config generation and reconcile
- `systemd` unit rendering and lifecycle management
- users, secrets, enable/disable, rotate, delete
- raw, `dd`, and `ee` secret export
- `tg://proxy` and `https://t.me/proxy` links
- health, logs, service preview, and cleanup flows

## 📦 Installation

```bash
source setup.sh
```

Installed console entrypoint:

```bash
mtproxy-manager
```

Manual path if you do not want the bootstrap script:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

## 🕹️ Usage

Default UI:

```bash
python3 mtp-manager.py
```

Console backend:

```bash
python3 mtp-manager.py --console
```

Dry run:

```bash
python3 mtp-manager.py --dry-run
```

Internal commands used by generated units:

```bash
python3 mtp-manager.py internal run-proxy
python3 mtp-manager.py internal refresh-proxy-config
python3 mtp-manager.py internal run-cleanup
```

## 🧰 Environment

- Python `3.11+`
- Debian or Ubuntu
- `systemd`
- root privileges for install, firewall, locale, cleanup, and service actions

Development override for managed state:

```bash
MTPROXY_MANAGER_STATE_ROOT=.devstate python3 mtp-manager.py --dry-run
```

`setup.sh` is intended to be launched only through `source` from both `bash` and `zsh`. It cleans stale `*.egg-info` and cache directories, creates `.venv`, installs Python dependencies, performs a smoke check, and activates the virtual environment automatically in the current shell.

## 📁 Managed Paths

- `/etc/mtproxy-manager`
- `/var/lib/mtproxy-manager`
- `/etc/systemd/system/mtproxy.service`
- `/etc/systemd/system/mtproxy-config-update.service`
- `/etc/systemd/system/mtproxy-config-update.timer`
- `/etc/systemd/system/mtproxy-cleanup.service`
- `/etc/systemd/system/mtproxy-cleanup.timer`
- `/opt/MTProxy`

## 🛡️ Safety Notes

- all shell execution is routed through the infra layer
- state and downloaded runtime artifacts are written atomically
- generated `systemd` units always launch the wrapper through the Python interpreter
- console mode remains available when `prompt_toolkit` is missing

## 📌 Status

The repository contains only the modular runtime code path and is ready for the first clean commit.
