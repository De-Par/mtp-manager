<h1 align="center">mtp-manager</h1>

<p align="center">
  TUI manager for
  <a href="https://github.com/telemt/telemt">telemt</a>
  on Debian and Ubuntu
</p>

<p align="center">
  Install, update, configure, and operate a telemt-based MTProto proxy from a compact terminal UI.
</p>

<p align="center">
  <a href="https://docs.python.org/3/">
    <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=FFD43B" alt="Python 3.11+">
  </a>
  <a href="https://textual.textualize.io/">
    <img src="https://img.shields.io/badge/textual-TUI-3FA34D?style=flat-square&logoColor=white" alt="Textual TUI">
  </a>
  <a href="https://ubuntu.com/server">
    <img src="https://img.shields.io/badge/platform-Debian%20%7C%20Ubuntu-E95420?style=flat-square&logoColor=white" alt="Debian or Ubuntu">
  </a>
  <a href="https://github.com/telemt/telemt">
    <img src="https://img.shields.io/badge/backend-telemt-2563EB?style=flat-square&logoColor=white" alt="telemt backend">
  </a>
</p>

<p align="center">
  <img src="assets/demo.png" alt="mtp-manager dashboard screenshot" width="88%">
</p>

## Features

- Install and update `telemt`
- Install a specific `tag` or `commit`
- Generate and refresh runtime configuration
- Manage `systemd` units and timers
- Manage users and secrets
- Export `raw`, `dd`, and `ee` secret formats
- View service status and logs
- Run cleanup tasks for logs, cache, and runtime artifacts


## Request Flow

The diagram below shows the high-level path of an MTProto message when `telemt` is used as the proxy layer with Fake TLS enabled.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "background": "#FFFFFF",
    "primaryTextColor": "#111827",
    "secondaryTextColor": "#111827",
    "tertiaryTextColor": "#111827",
    "lineColor": "#111827",
    "fontSize": "18px",
    "fontFamily": "Arial, sans-serif"
  }
}}%%

flowchart TD

    subgraph MAIN["MTProto over Fake TLS"]
        direction TB

        subgraph ROW1[" "]
            direction LR
            C("Telegram client<br/><br/>• Build request<br/>• Encrypt payload<br/>• Wrap in Fake TLS")
            N("Network path<br/><br/>• Carry outer flow<br/>• Hide plaintext")
        end

        subgraph ROW2[" "]
            direction LR
            P("telemt proxy<br/><br/>• Accept session<br/>• Validate secret<br/>• Remove disguise<br/>• Forward ciphertext")
            T("Telegram backend<br/><br/>• Resolve session<br/>• Decrypt packet<br/>• Process message<br/>• Store update")
        end

        subgraph ROW3[" "]
            direction LR
            R("Recipient client<br/><br/>• Receive update<br/>• Decrypt payload<br/>• Render message")
            D("Delivery status<br/><br/>• Confirm ACK<br/>• Track delivered / read")
        end

        C ==> N
        N ==> P
        P ==> T
        T ==> R
        R ==> D

        T -. "server ack" .-> C
        D -. "delivered / read" .-> C
    end

    classDef client fill:#DBEAFE,stroke:#1D4ED8,stroke-width:3px,color:#0F172A
    classDef network fill:#F3E8FF,stroke:#7C3AED,stroke-width:3px,color:#0F172A
    classDef proxy fill:#FFEDD5,stroke:#EA580C,stroke-width:3px,color:#0F172A
    classDef core fill:#DCFCE7,stroke:#16A34A,stroke-width:3px,color:#0F172A
    classDef recipient fill:#FCE7F3,stroke:#DB2777,stroke-width:3px,color:#0F172A
    classDef delivery fill:#E5E7EB,stroke:#374151,stroke-width:3px,color:#0F172A

    class C client
    class N network
    class P proxy
    class T core
    class R recipient
    class D delivery

    style MAIN fill:#FFFFFF,stroke:#111827,stroke-width:4px,color:#111827
    style ROW1 fill:#FFFFFF,stroke:#FFFFFF
    style ROW2 fill:#FFFFFF,stroke:#FFFFFF
    style ROW3 fill:#FFFFFF,stroke:#FFFFFF

    linkStyle default stroke:#111827,stroke-width:3px
```

## Quick Start

```bash
source setup.sh
mtp-manager
```

`setup.sh` is designed to be loaded with `source` from `bash` or `zsh`. It prepares `.venv`, installs the project in editable mode, validates the installed entrypoint, and activates the environment in the current shell.

## Requirements

- Python `3.11+`
- Debian or Ubuntu
- `systemd`
- root privileges for install, service, firewall, locale, and cleanup actions

## Project Layout

| Path | Purpose |
| --- | --- |
| `src/app.py` | CLI entrypoint and internal service commands |
| `src/bootstrap.py` | Dependency wiring and startup migration glue |
| `src/controller.py` | Application-level actions used by the TUI |
| `src/services/` | `telemt` install, runtime, diagnostics, cleanup, inventory |
| `src/infra/` | Shell, storage, locale, public IP, firewall, `systemd` |
| `src/ui/textual_app.py` | Main TUI orchestration |
| `src/ui/modals.py` | Modal screens and shared popup UI |
| `src/ui/dashboard.py` | Dashboard rendering and host metrics |
| `src/ui/actions.py` | Action definitions and menu helpers |
| `src/ui/lists.py` | Sections, users, and secrets list helpers |
| `src/models/` | Typed domain models |
| `src/i18n/` | EN and RU catalogs |

## Managed Paths

- config directory: `/etc/mtp-manager`
- app data: `/var/lib/mtp-manager`
- binary directory: `/opt/telemt`
- main unit: `/etc/systemd/system/telemt.service`
- config refresh unit/timer:
  - `/etc/systemd/system/telemt-config-update.service`
  - `/etc/systemd/system/telemt-config-update.timer`
- cleanup unit/timer:
  - `/etc/systemd/system/telemt-cleanup.service`
  - `/etc/systemd/system/telemt-cleanup.timer`

## Notes

- shell execution is routed through the infra layer
- generated files are written atomically
- managed `systemd` units invoke the installed `mtp-manager` entrypoint
- the project includes migration logic for older `mtproxy`-based layouts
