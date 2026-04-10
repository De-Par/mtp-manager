<h1 align="center">mtp-manager</h1>

<p align="center">
  Minimal terminal UI for managing
  <a href="https://github.com/telemt/telemt">telemt</a>
  on Debian, Ubuntu, Fedora, and Arch Linux
</p>

<p align="center">
  <a href="https://docs.python.org/3/">
    <img src="https://img.shields.io/badge/Python-3.11%2B-1D4ED8?style=flat-square&logoColor=white" alt="Python 3.11+">
  </a>
  <a href="https://textual.textualize.io/">
    <img src="https://img.shields.io/badge/Textual-TUI-15803D?style=flat-square&logoColor=white" alt="Textual TUI">
  </a>
  <a href="https://ubuntu.com/server">
    <img src="https://img.shields.io/badge/Platform-Debian%20%7C%20Ubuntu%20%7C%20Fedora%20%7C%20Arch-EA580C?style=flat-square&logoColor=white" alt="Debian, Ubuntu, Fedora, or Arch Linux">
  </a>
  <a href="https://github.com/telemt/telemt">
    <img src="https://img.shields.io/badge/Backend-telemt-0F766E?style=flat-square&logoColor=white" alt="telemt backend">
  </a>
</p>

<p align="center">
  <a href="src/i18n/en.py">
    <img src="https://img.shields.io/badge/Language-English-7C3AED?style=flat-square&logoColor=white" alt="English UI">
  </a>
  <a href="src/i18n/ru.py">
    <img src="https://img.shields.io/badge/Language-Русский-DB2777?style=flat-square&logoColor=white" alt="Russian UI">
  </a>
  <a href="src/i18n/zh.py">
    <img src="https://img.shields.io/badge/Language-中文-CA8A04?style=flat-square&logoColor=white" alt="Chinese UI">
  </a>
</p>

<p align="center">
  <img src="assets/demo.png" alt="mtp-manager dashboard screenshot" width="84%">
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
