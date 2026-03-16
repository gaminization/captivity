# Changelog

All notable changes to the Captivity project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [v1.0] — 2026-03-16

### Added

- `core/state.py` — connection state machine (INIT → CONNECTED lifecycle)
- `captivity networks` CLI subcommand

### Changed

- `core/login.py` — rewritten for plugin-based portal login with cache fast-path
- `daemon/runner.py` — integrates event bus, DBus monitor, state machine, auto-SSID
- Version bumped to 1.0.0

### Tests

- `test_state.py` (12 tests), updated `test_login.py` (6 tests)
- Total: 114 Python tests + 40 shell tests = 154 tests passing

---

## [v0.9] — 2026-03-16

### Added
- `daemon/events.py` — thread-safe event bus (subscribe/publish)
    - Events: NETWORK_CONNECTED, PORTAL_DETECTED, LOGIN_SUCCESS, LOGIN_FAILURE, SESSION_EXPIRED, SYSTEM_RESUME, DAEMON_START/STOP
- `daemon/dbus_monitor.py` — NetworkManager state monitor via busctl/nmcli
    - Connectivity state queries (NONE, PORTAL, LIMITED, FULL)
    - Active WiFi SSID detection
    - System resume detection via logind
    - Falls back to polling when DBus unavailable
- `tests/python/test_events.py` — 10 event bus tests
- `tests/python/test_dbus_monitor.py` — 12 DBus monitor tests

---

## [v0.8] — 2026-03-16

### Added
- Plugin architecture: `plugins/base.py` abstract base class
- `plugins/pronto.py` — Pronto Networks plugin (extracted from login engine)
- `plugins/generic.py` — Generic plugin using HTML form parser (fallback)
- `plugins/loader.py` — priority-based plugin discovery (built-in + entry_points)
- `captivity plugins` CLI subcommand to list installed plugins
- `tests/python/test_plugins.py` — 19 plugin tests

---

## [v0.7] — 2026-03-16

### Added
- `core/parser.py` — dynamic HTML form parser for arbitrary captive portals
- Automatic field detection (username/password by name patterns and input type)
- Form payload builder with hidden field preservation
- `core/cache.py` — portal endpoint cache (JSON, XDG-compliant, 7-day TTL)
- `tests/python/test_parser.py` — 15 parser tests
- `tests/python/test_cache.py` — 10 cache tests

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
