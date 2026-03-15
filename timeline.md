# Captivity — Development Timeline

## Version Roadmap

| Version | Milestone                          | Status      |
|---------|-------------------------------------|-------------|
| v0.1    | Initial login script               | ✅ Released  |
| v0.2    | Secure credential storage          | ✅ Released  |
| v0.3    | Automatic reconnect loop           | ✅ Released  |
| v0.4    | NetworkManager dispatcher          | ✅ Released  |
| v0.5    | Systemd daemon service             | ✅ Released  |
| v0.6    | Python core rewrite                | ✅ Released  |
| v0.7    | Dynamic portal login parsing       | ✅ Released  |
| v0.8    | Plugin architecture                | ✅ Released  |
| v0.9    | NetworkManager DBus events         | 🔲 Planned  |
| v1.0    | Stable captive portal client       | 🔲 Planned  |
| v1.1    | Tray UI + notifications            | 🔲 Planned  |
| v1.2    | Automatic network learning         | 🔲 Planned  |
| v1.3    | Telemetry + bandwidth monitoring   | 🔲 Planned  |
| v1.4    | Local web dashboard                | 🔲 Planned  |
| v1.5    | Smart retry system                 | 🔲 Planned  |
| v1.6    | Connection state machine           | 🔲 Planned  |
| v1.7    | Portal simulator                   | 🔲 Planned  |
| v1.8    | Plugin marketplace                 | 🔲 Planned  |
| v1.9    | Configuration system               | 🔲 Planned  |
| v2.0    | Rust networking daemon core        | 🔲 Planned  |

## Release History

### v0.8 — 2026-03-16
- Plugin base class, Pronto + Generic plugins
- Priority-based loader with entry_points support
- 19 new tests

### v0.7 — 2026-03-16
- Dynamic HTML form parser for arbitrary portals
- Portal endpoint cache with 7-day TTL
- 25 new tests (parser + cache)

### v0.6 — 2026-03-16
- Python package structure with `src/captivity/`
- Connectivity probe, credential wrapper, login engine in Python
- CLI: `captivity login|probe|status|daemon|creds`
- 34 Python tests passing

### v0.5 — 2026-03-16
- Systemd service unit with security hardening
- Auto-restart on failure, journal logging
- Service installer with enable/start/uninstall

### v0.4 — 2026-03-16
- NetworkManager dispatcher integration
- Auto-login on WiFi connect and connectivity changes
- Installer with config template

### v0.3 — 2026-03-16
- Automatic reconnect loop with connectivity probing
- Exponential backoff retry (5s → 300s)
- Single probe and daemon modes

### v0.2 — 2026-03-16
- Secure credential storage via `secret-tool`
- Enhanced login script with CLI flags
- Test suite and documentation

### v0.1 — Initial Release
- Pronto Networks captive portal login via `curl`
- Basic connectivity verification
