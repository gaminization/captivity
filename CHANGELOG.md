# Changelog

All notable changes to the Captivity project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
