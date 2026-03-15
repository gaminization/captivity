# Captivity

![Status](https://img.shields.io/badge/status-v0.7--alpha-yellow)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

An autonomous login client for WiFi captive portals.

Automatically logs into captive portal networks so you don't have to open a browser every time.

---

## Why This Exists

Many campus and public WiFi networks require users to repeatedly log into a captive portal.

Typical workflow:

1. connect to WiFi
2. open a browser
3. wait for the portal redirect
4. enter credentials

Captivity removes this manual step by automating the login process.

---

## Features

### v0.7 — Dynamic Portal Login Parsing
* Automatic HTML form detection and parsing (stdlib only)
* Smart field identification (username/password by name patterns)
* Portal endpoint cache for fast re-login (7-day TTL)
* Supports arbitrary captive portals without hardcoded form fields

### v0.6 — Python Core Rewrite
* Full Python package: `src/captivity/` with modular architecture
* CLI entry point: `captivity login|probe|status|daemon|creds`
* Connectivity probe via `requests` (replaces curl)
* Login engine using `requests.Session`
* Secure credentials via `secret-tool` wrapper
* Reconnect daemon with exponential backoff
* Structured logging with ISO timestamps
* 34 Python unit tests

### v0.5 — Systemd Daemon Service
* Run as a background system daemon via `systemd`
* Automatic startup on boot
* Journal logging (`journalctl -u captivity`)
* Auto-restart on failure
* Security hardening (NoNewPrivileges, ProtectSystem)

### v0.4 — NetworkManager Dispatcher Integration
* Automatic login when WiFi connects via NetworkManager dispatcher
* Detects WiFi interfaces (wlan*, wlp*, wlo*)
* Triggers on `up` and `connectivity-change` events
* Configuration via `/etc/captivity/config`
* Syslog logging

### v0.3 — Automatic Reconnect Loop
* Connectivity probing via `https://clients3.google.com/generate_204`
* HTTP 204 = connected, redirect = captive portal detected
* Exponential backoff retry (5s → 10s → 30s → 60s → 120s → 300s)
* `--once` mode for single connectivity check
* `--daemon` mode for continuous monitoring
* Graceful shutdown on SIGTERM/SIGINT

### v0.2 — Secure Credential Storage
* Secure credential management via Linux Secret Service (`secret-tool`)
* Store, retrieve, and delete credentials per network
* Enhanced login script with CLI flags (`--network`, `--portal`, `--dry-run`)
* No plaintext credentials

### v0.1 — Legacy
* Login to a Pronto Networks captive portal
* Uses `curl` for authentication requests
* Performs a connectivity check after login

---

## Quick Start

### Prerequisites

- `curl`
- `secret-tool` (from `libsecret-tools`)

Install dependencies:

```bash
# Debian/Ubuntu
sudo apt install curl libsecret-tools

# Fedora
sudo dnf install curl libsecret

# Arch
sudo pacman -S curl libsecret
```

### Installation

Clone the repository:

```bash
git clone https://github.com/gaminization/captivity.git
cd captivity
```

### Store Credentials

```bash
bash scripts/captivity-creds.sh store my_campus_wifi
# Enter username and password when prompted
```

### Login

```bash
bash scripts/captivity-login.sh --network my_campus_wifi
```

With a custom portal URL:

```bash
bash scripts/captivity-login.sh --network my_campus_wifi --portal http://portal.example.com/login
```

Test without making network requests:

```bash
bash scripts/captivity-login.sh --network my_campus_wifi --dry-run
```

### Python CLI (v0.6+)

```bash
# Install
pip3 install .

# Login
captivity login --network <SSID>

# Check status
captivity status

# Probe connectivity
captivity probe

# Run daemon
captivity daemon --network <SSID>

# Manage credentials
captivity creds store <SSID>
captivity creds list
```

### Legacy Shell Scripts (v0.2–v0.5)

The original v0.1 script still works:

```bash
# Edit login.sh with your credentials, then:
./login.sh
```

---

## Credential Management

```bash
# Store credentials for a network
bash scripts/captivity-creds.sh store <network>

# Retrieve credentials
bash scripts/captivity-creds.sh retrieve <network>

# Delete credentials
bash scripts/captivity-creds.sh delete <network>

# List stored networks
bash scripts/captivity-creds.sh list
```

---

## Running Tests

```bash
bash tests/test_credentials.sh
bash tests/test_login.sh
bash tests/test_reconnect.sh
PYTHONPATH=src python3 -m pytest tests/python/ -v
```

---

## Repository Structure

```
captivity/
├── login.sh                    # Original v0.1 script (preserved)
├── scripts/
│   ├── captivity-creds.sh      # Credential management CLI
│   ├── captivity-login.sh      # Enhanced login script
│   ├── captivity-reconnect.sh  # Reconnect loop with probing
│   ├── captivity-dispatcher.sh # NetworkManager dispatcher hook
│   ├── install-dispatcher.sh   # Dispatcher installer
│   └── install-service.sh      # Service installer
├── src/captivity/                  # Python core (v0.6+)
│   ├── cli.py                  # CLI dispatcher
│   ├── core/
│   │   ├── probe.py            # Connectivity probing
│   │   ├── credentials.py      # secret-tool wrapper
│   │   └── login.py            # Login engine
│   ├── daemon/
│   │   └── runner.py           # Reconnect daemon
│   └── utils/
│       └── logging.py          # Structured logging
├── systemd/
│   └── captivity.service       # Systemd unit file
├── tests/
│   ├── test_credentials.sh     # Credential tests
│   ├── test_reconnect.sh       # Reconnect loop tests
│   ├── test_dispatcher.sh      # Dispatcher tests
│   └── python/                 # Python tests (34 tests)
│       ├── test_probe.py
│       ├── test_credentials.py
│       ├── test_login.py
│       └── test_cli.py
│   └── test_login.sh           # Login tests
├── docs/
│   └── architecture.md         # Architecture overview
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CONTRIBUTORS.md
├── timeline.md
└── LICENSE
```

---

## Roadmap

See [timeline.md](timeline.md) for the full version roadmap.

**Next:** v0.8 — Plugin architecture.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the Apache 2.0 License.
