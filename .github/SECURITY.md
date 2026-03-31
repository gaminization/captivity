# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Captivity, please report it responsibly.

### How to Report

1. **Do NOT open a public issue.** Security vulnerabilities must be reported privately.
2. Use [GitHub Security Advisories](https://github.com/gaminization/captivity/security/advisories/new) to submit a private report.
3. Alternatively, email: **garvarora@gmail.com**

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

### Response Timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 5 business days
- **Fix and disclosure**: coordinated with reporter

### Scope

The following are in scope:

- Credential storage and retrieval
- Network communication (probe, login, IPC)
- systemd service configuration
- Plugin loading and execution

### Security Measures

Captivity implements the following security practices:

- **CodeQL scanning** on every push to `main`
- **No plaintext credentials** — keyring-backed via OS secret service
- **systemd hardening** — `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`
- **Dependency scanning** via Dependabot (when enabled)
- **Sandboxed execution** — read-only home, strict filesystem boundaries

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | ✅        |
| 1.x     | ⚠️ Security fixes only |
| < 1.0   | ❌        |
