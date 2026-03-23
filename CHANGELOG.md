# Changelog

All notable changes to the Captivity project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [v2.0] — 2026-03-24

### Added

- `daemon-rs/` — Rust networking daemon core
  - `src/probe.rs` — HTTP 204 connectivity probing
  - `src/monitor.rs` — Network state tracking with event emission
  - `src/ipc.rs` — Unix domain socket IPC server (JSON protocol)
  - `src/main.rs` — Event loop, CLI args, signal handling
  - Minimal deps: ureq, serde, serde_json
  - Release profile: LTO, strip, size-optimized
- `daemon/bridge.py` — Python ↔ Rust IPC bridge
  - Unix socket client with JSON commands
  - Event subscription with background thread
  - Daemon process launcher
- `captivity daemon-rs` CLI subcommand
  - `daemon-rs` — start Rust daemon
  - `daemon-rs status` — query connectivity
  - `daemon-rs stop` — stop daemon
  - `daemon-rs probe` — request immediate probe

### Tests

- `test_bridge.py` (16 tests) — Python bridge with mock socket server
- Rust unit tests (11 tests in probe/monitor/ipc modules)
- Total: 377 Python tests + 40 shell + 11 Rust = 428 tests

---

## [v1.9] — 2026-03-23

### Added

- `core/config.py` — layered configuration system
  - 8 typed sections: probe, daemon, dashboard, simulator, plugins, telemetry, tray, login
  - TOML file support (stdlib tomllib or fallback parser)
  - Environment variable overrides (CAPTIVITY_SECTION_KEY)
  - Type-safe coercion (str→int/float/bool)
  - Singleton accessor, save/load/generate
- `captivity config` CLI subcommand
  - `config show` — display all settings
  - `config get <key>` — read a value
  - `config set <key> <value>` — write a value
  - `config init` — generate default config file
  - `config reset` — restore defaults

### Tests

- `test_config.py` (34 tests)
- Total: 361 Python tests + 40 shell tests = 401 tests passing

---

## [v1.8] — 2026-03-23

### Added

- `plugins/registry.py` — local plugin registry (JSON persistence)
  - PluginEntry dataclass with package, version, source, portal_types
  - Register, unregister, list, persistence, corruption handling
- `plugins/marketplace.py` — plugin marketplace
  - Built-in catalog: Cisco, Aruba, CoovaChilli, Fortinet, MikroTik, UniFi
  - Search by name, portal type, or keyword
  - pip-based install/uninstall with registry tracking
- Enhanced `captivity plugins` CLI:
  - `plugins search [query]` — search marketplace
  - `plugins install <package>` — install from PyPI
  - `plugins uninstall <package>` — remove plugin
  - `plugins info <package>` — show plugin details
  - `plugins installed` — list marketplace plugins

### Tests

- `test_registry.py` (12 tests)
- `test_marketplace.py` (14 tests)
- Total: 327 Python tests + 40 shell tests = 367 tests passing

---

## [v1.7] — 2026-03-23

### Added

- `testing/` subpackage for portal simulation
- `testing/simulator.py` — captive portal emulator using stdlib http.server
  - Login pages, HTTP 302 redirects, connectivity probes (204)
  - Session management with configurable expiry
  - Rate limiting, flaky failure simulation
  - Terms acceptance, custom form fields
  - JSON status and scenario info endpoints
  - Context manager support for test automation
- `testing/scenarios.py` — 9 built-in test scenarios
  - simple, terms, redirect, session_expiry, rate_limited
  - flaky, slow, custom_fields, email_only
- `captivity simulate` CLI subcommand with --port, --scenario, --list

### Tests

- `test_scenarios.py` (13 tests)
- `test_simulator.py` (13 integration tests)
- Total: 297 Python tests + 40 shell tests = 337 tests passing

---

## [v1.6] — 2026-03-23

### Enhanced

- `core/state.py` — connection state machine v2
  - New RETRY_WAIT state for smart retry integration
  - Transition history tracking (capped at 100 records)
  - State duration measurement per transition
  - RetryEngine auto-integration (success/failure recording)
  - Event bus auto-publishing on state transitions
  - `TransitionRecord` dataclass for typed history
  - New properties: `is_waiting`, `state_duration`, `transition_count`
  - `get_state_stats()` for per-state time analysis
  - Full backward compatibility with v1.0 API

### Tests

- Updated `test_state.py` for 8 states
- Total: 271 Python tests + 40 shell tests = 311 tests passing

---

## [v1.5] — 2026-03-23

### Added

- `core/retry.py` — smart retry engine with adaptive backoff

### Features

- Exponential backoff with additive jitter
- Failure classification: transient, auth, rate-limited, portal-down
- Per-type backoff multipliers (rate-limited: 2x, portal-down: 3x)
- Sliding window rate limiter (5 attempts per 60s default)
- Circuit breaker: auto-opens on auth errors or max attempts, auto-resets
- Error string classifier for automatic failure categorization

### Tests

- `test_retry.py` (22 tests)
- Total: 271 Python tests + 40 shell tests = 311 tests passing

---

## [v1.4] — 2026-03-23

### Added

- `dashboard/` subpackage — local web dashboard at `http://localhost:8787`
- `dashboard/api.py` — JSON API (5 endpoints: status, stats, history, networks, bandwidth)
- `dashboard/server.py` — stdlib HTTP server, localhost-only binding
- `dashboard/page.py` — embedded dark-theme SPA with auto-refresh
- `captivity dashboard` CLI subcommand (--port configurable)

### Features

- Dark theme with gradient accents, status cards, network table, event history
- Auto-refresh every 5 seconds via fetch API
- Zero external dependencies — built on Python’s http.server
- Background thread mode for daemon integration

### Tests

- `test_dashboard_api.py` (15 tests), `test_dashboard_server.py` (5 integration tests)
- Total: 247 Python tests + 40 shell tests = 287 tests passing

---

## [v1.3] — 2026-03-23

### Added

- `telemetry/session.py` — WiFi session uptime tracking
- `telemetry/bandwidth.py` — bandwidth monitoring via /proc/net/dev
- `telemetry/stats.py` — persistent connection statistics database
- `captivity stats` CLI subcommand (summary + history views)

### Features

- Per-network statistics: login success/failure rates, uptime, bandwidth
- Connection event history (capped at 500 entries)
- Zero-dependency bandwidth monitoring using kernel counters
- Auto-detection of WiFi interface (wl* pattern)

### Tests

- `test_session.py` (14 tests), `test_bandwidth.py` (15 tests), `test_stats.py` (13 tests)
- Total: 229 Python tests + 40 shell tests = 269 tests passing

---

## [v1.2] — 2026-03-23

### Added

- `core/fingerprint.py` — network fingerprinting (gateway IP/MAC, portal domain, content hash)
- `core/profiles.py` — persistent network profile database with auto-learning
- `captivity learn` CLI subcommand (list, show, forget)

### Features

- Weighted similarity matching for recognizing known networks
- Automatic profile creation on successful login
- Network profile stores: fingerprint, plugin preference, login history, cached endpoint
- Fingerprint-based instant portal recognition

### Tests

- `test_fingerprint.py` (18 tests), `test_profiles.py` (16 tests)
- Total: 178 Python tests + 40 shell tests = 218 tests passing

---

## [v1.1] — 2026-03-16

### Added

- `ui/` subpackage for graphical components
- `ui/notifier.py` — desktop notifications via `notify-send`
- `ui/tray.py` — GTK3 system tray icon with event-driven status updates
- `captivity tray` CLI subcommand to launch tray icon

### Features

- Notifications for: login success/failure, portal detected, session expired, daemon start
- Tray icon with context menu (Probe, Login, Quit)
- Event bus integration — icon and notifications update automatically
- Graceful degradation when GTK3 or notify-send unavailable

### Tests

- `test_notifier.py` (12 tests), `test_tray.py` (10 tests)
- Total: 137 Python tests + 40 shell tests = 177 tests passing

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
