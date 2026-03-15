# Changelog

All notable changes to the Captivity project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [v0.6] — 2026-03-16

### Added
- Python package structure: `src/captivity/` with `core/`, `daemon/`, `utils/` subpackages
- `core/probe.py` — connectivity probing via `requests` (replaces curl)
- `core/credentials.py` — `secret-tool` wrapper in Python
- `core/login.py` — Pronto Networks login engine using `requests.Session`
- `daemon/runner.py` — reconnect loop with exponential backoff and signal handling
- `utils/logging.py` — structured logging with ISO timestamps
- `cli.py` — CLI dispatcher: `captivity login|probe|status|daemon|creds`
- `pyproject.toml` — package metadata, `requests` dependency, `captivity` entry point
- Python test suite: 34 tests (probe, credentials, login, CLI)

### Changed
- `systemd/captivity.service` — ExecStart now uses `python3 -m captivity daemon`

---

## [v0.5] — 2026-03-16

### Added
- `systemd/captivity.service` — systemd service unit for background daemon
- Security hardening (NoNewPrivileges, ProtectSystem, PrivateTmp)
- Automatic restart on failure with 10s delay
- Journal logging via stdout/stderr
- `scripts/install-service.sh` — install/enable/start/uninstall service

---

## [v0.4] — 2026-03-16

### Added
- `scripts/captivity-dispatcher.sh` — NetworkManager dispatcher hook
- Automatic login trigger on WiFi `up` and `connectivity-change` events
- WiFi interface detection (wlan*, wlp*, wlo* patterns + sysfs check)
- `scripts/install-dispatcher.sh` — install/uninstall dispatcher with config template
- Configuration file support at `/etc/captivity/config`
- Syslog logging via `logger`
- `tests/test_dispatcher.sh` — dispatcher and installer tests

---

## [v0.3] — 2026-03-16

### Added
- `scripts/captivity-reconnect.sh` — automatic reconnect loop with connectivity probing
- Connectivity probe using `https://clients3.google.com/generate_204`
- Exponential backoff retry: 5s → 10s → 30s → 60s → 120s → 300s
- `--once` mode for single probe, `--daemon` mode for continuous operation
- Graceful shutdown via SIGTERM/SIGINT signal handling
- `tests/test_reconnect.sh` — reconnect loop tests

---

## [v0.2] — 2026-03-16

### Added
- Secure credential storage using Linux Secret Service (`secret-tool`)
- `scripts/captivity-creds.sh` — credential management CLI (store/retrieve/delete/list)
- `scripts/captivity-login.sh` — enhanced login with `--network`, `--portal`, `--dry-run` flags
- Test suite: `tests/test_credentials.sh`, `tests/test_login.sh`
- Project documentation: CONTRIBUTING.md, CONTRIBUTORS.md, timeline.md
- Architecture documentation: `docs/architecture.md`

### Changed
- `login.sh` — added legacy header comment (no functional changes)
- `README.md` — updated with v0.2 features and credential setup instructions

---

## [v0.1] — 2025-01-01

### Added
- Initial release
- `login.sh` — Pronto Networks captive portal login via `curl`
- Basic connectivity check after login
