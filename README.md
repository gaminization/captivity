<p align="center">
  <h1 align="center">Captivity</h1>
  <p align="center">
    <strong>Autonomous captive portal login client for WiFi networks.</strong><br/>
    Connect → Authenticate → Online. Instantly.
  </p>
</p>

<p align="center">
  <a href="https://github.com/gaminization/captivity/releases"><img src="https://img.shields.io/badge/version-2.0.0-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/gaminization/captivity/actions/workflows/ci.yml"><img src="https://img.shields.io/badge/CI-passing-brightgreen?style=flat-square" alt="CI"></a>
  <a href="https://github.com/gaminization/captivity/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-orange?style=flat-square" alt="License"></a>
  <a href="https://pypi.org/project/captivity/"><img src="https://img.shields.io/badge/python-3.8%2B-yellow?style=flat-square" alt="Python"></a>
  <a href="https://github.com/gaminization/captivity/actions/workflows/codeql.yml"><img src="https://img.shields.io/badge/security-CodeQL-purple?style=flat-square" alt="CodeQL"></a>
</p>

---

## Why

Every hotel, airport, and coffee shop makes you do the same thing:

```
❌  Connect → Open browser → Wait for redirect → Find the button → Click → Wait → Maybe it works
```

Captivity eliminates the entire process:

```
✅  Connect → Auto-login (~150ms) → Online
```

No browser. No clicking. No waiting. Your device connects to WiFi, Captivity detects the portal, authenticates, and gets you online before you even notice.

---

## Features

### Core

- **Automatic portal detection** — HTTP 204 probing with redirect analysis
- **Plugin-based login** — Modular handlers for any portal type
- **Credential vault** — Encrypted storage with `keyring` integration
- **Network learning** — Fingerprints portals, remembers successful strategies

### Performance

| Metric | Value |
|--------|-------|
| Portal detection | < 50 ms |
| Login execution | < 200 ms |
| Memory (Python) | ~ 15 MB |
| Memory (Rust daemon) | < 10 MB |
| Background polling | configurable (default 30s) |

### System Integration

- **systemd service** — runs as a background daemon
- **D-Bus monitoring** — reacts to NetworkManager events
- **System tray** — GTK status icon with notifications
- **Web dashboard** — real-time stats at `localhost:8787`

### Security

- **CodeQL scanning** — automated on every push
- **No plaintext credentials** — keyring-backed storage
- **systemd hardening** — `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`
- **Sandboxed daemon** — read-only home, strict filesystem access

### Multi-Network

- **Network profiles** — per-SSID portal fingerprints and strategies
- **Plugin marketplace** — community-contributed portal handlers
- **Endpoint caching** — skip redundant probes on known networks

---

## How It Works

```
┌──────────┐     ┌───────────────┐     ┌──────────┐     ┌──────────┐
│  detect  │────▶│  parse portal │────▶│  login   │────▶│  verify  │
└──────────┘     └───────────────┘     └──────────┘     └──────────┘
  HTTP 204         HTML analysis        Plugin match       Re-probe
  probe            form extraction      auto-submit        confirm 204
```

1. **Detect** — Sends a lightweight HTTP request to `clients3.google.com/generate_204`. A `204` means connected. A redirect means captive portal.
2. **Parse** — Extracts login forms, hidden fields, and action URLs from the portal page.
3. **Login** — Matches the portal to a plugin (or uses the generic handler), submits credentials.
4. **Verify** — Re-probes to confirm internet access. Caches the result for future connections.

The daemon runs this pipeline continuously, reacting to network changes via D-Bus and re-authenticating when sessions expire.

---

## Installation

### pip (recommended)

```bash
pip install captivity
```

### Homebrew

```bash
brew tap gaminization/captivity
brew install captivity
```

### From source

```bash
git clone https://github.com/gaminization/captivity.git
cd captivity
pip install -e ".[dev]"
```

Verify the installation:

```bash
captivity --help
```

---

## Usage

### Quick Start

```bash
# One-shot login
captivity login

# Check connectivity status
captivity status

# Run as background daemon
captivity daemon
```

### Credential Management

```bash
# Store credentials for a network
captivity creds set --network "Airport WiFi" --username user --password pass

# List stored networks
captivity creds list
```

### Configuration

```bash
# Show all settings
captivity config show

# Set a value
captivity config set probe.timeout 3

# Generate default config file
captivity config init
```

Config file location: `~/.config/captivity/config.toml`

Priority: **Environment variables** > **Config file** > **Built-in defaults**

Environment override format: `CAPTIVITY_SECTION_KEY` (e.g., `CAPTIVITY_PROBE_TIMEOUT=3`)

---

## System Integration

### systemd

```bash
sudo cp systemd/captivity.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now captivity
```

Check status:

```bash
sudo systemctl status captivity
journalctl -u captivity -f
```

### System Tray

```bash
captivity tray
```

Shows connection status as a GTK tray icon with desktop notifications on state changes.

---

## Dashboard

```bash
captivity dashboard
```

Opens a local web dashboard at **http://localhost:8787** showing:

- Current connection status
- Login success/failure history
- Session uptime and bandwidth
- Network profile statistics

---

## Plugin System

Captivity uses a plugin architecture for portal-specific login handlers.

### Built-in Plugins

- `generic` — universal form-based handler
- `pronto` — Oroneto/Pronto portal networks

### Marketplace

```bash
# Search available plugins
captivity plugins search cisco

# Install a community plugin
pip install captivity-plugin-cisco

# List installed plugins
captivity plugins installed
```

### Writing a Plugin

```python
from captivity.plugins.base import CaptivePortalPlugin

class MyPortalPlugin(CaptivePortalPlugin):
    name = "my-portal"
    
    def detect(self, url: str, html: str) -> bool:
        return "My Portal" in html
    
    def login(self, url: str, html: str, credentials: dict) -> bool:
        # Submit login form
        return True
```

Register via `entry_points` in your package's `pyproject.toml`:

```toml
[project.entry-points."captivity.plugins"]
my-portal = "my_plugin:MyPortalPlugin"
```

---

## Testing and CI

### Running Tests

```bash
# Python tests (377 tests)
PYTHONPATH=src python3 -m pytest tests/python/ -v

# Shell tests (40 tests)
for f in tests/test_*.sh; do bash "$f"; done

# Rust daemon tests (requires cargo)
cd daemon-rs && cargo test
```

### CI Pipeline

GitHub Actions runs on every push and PR:

| Step | Tool | Policy |
|------|------|--------|
| Lint | `pylint` (errors only) | non-blocking |
| Test | `pytest` + `pytest-cov` | coverage report |
| Security | CodeQL | Python analysis |
| Publish | `twine` | on GitHub Release |

---

## Security

- **CodeQL** — automated vulnerability scanning on every push to `main`
- **Credential isolation** — passwords stored via OS keyring, never in config files
- **systemd hardening** — sandboxed with `NoNewPrivileges`, `ProtectSystem=strict`
- **No root required** — runs as unprivileged user

Report security issues via [GitHub Security Advisories](https://github.com/gaminization/captivity/security).

---

## Advanced

### Smart Retry

Exponential backoff with jitter, configurable max attempts and ceiling. Circuit breaker pattern prevents hammering failing portals.

### State Machine

Tracks connection lifecycle: `IDLE → PROBING → DETECTED → LOGGING_IN → CONNECTED → SESSION_EXPIRED`. Each transition emits events on the internal event bus.

### Portal Simulator

```bash
# Run a simulated captive portal for testing
captivity simulate --scenario rate_limited --port 8888
```

9 built-in scenarios: `simple`, `terms`, `redirect`, `session_expiry`, `rate_limited`, `flaky`, `slow`, `custom_fields`, `email_only`.

### Network Learning

Captivity fingerprints portal pages and stores successful login strategies per network. On reconnection, it skips detection and replays the known strategy.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              captivity daemon               │
                    │                                             │
  NetworkManager ──▶│  D-Bus Monitor ──▶ Event Bus ──▶ Plugins   │
  (D-Bus events)    │       │                │                    │
                    │       ▼                ▼                    │
                    │  Network Monitor    Session Tracker         │
                    │  (probe loop)       (stats, bandwidth)     │
                    └──────────┬──────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Rust Daemon (v2)  │
                    │   probe · monitor   │◀── Unix Socket IPC
                    │   ipc · events      │
                    └─────────────────────┘
```

**Python** handles: CLI, plugins, UI, dashboard, configuration, credentials.

**Rust** handles: low-level networking, high-frequency probing, event dispatch.

Communication via Unix domain socket with newline-delimited JSON.

---

## Roadmap

- [ ] Rust daemon as default network core
- [ ] Plugin ecosystem with registry API
- [ ] macOS and Windows support
- [ ] WPA Enterprise / 802.1X detection
- [ ] Mobile companion (Android)

See [timeline.md](timeline.md) for the full version history.

---

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Branch strategy (`feature → dev → release → main`)
- Commit conventions (Conventional Commits)
- Testing requirements
- Release process

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

<p align="center">
  <em>WiFi should just work. Captivity makes sure it does.</em>
</p>
