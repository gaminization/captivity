# Contributing to Captivity

Thank you for your interest in contributing to Captivity!

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/captivity.git
   cd captivity
   ```
3. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Guidelines

### Code Style
- **Shell scripts**: Use `set -euo pipefail`, quote all variables, use `readonly` for constants
- **Functions**: Use descriptive names with `snake_case`
- **Comments**: Add a file header explaining purpose and usage

### Testing
- All scripts must have corresponding test files in `tests/`
- Tests must produce TAP-compatible output
- Run all tests before submitting:
  ```bash
  for f in tests/test_*.sh; do bash "$f"; done
  ```
- Validate syntax:
  ```bash
  for f in scripts/*.sh tests/*.sh; do bash -n "$f"; done
  ```

### Commits
- Use clear, descriptive commit messages
- Reference issue numbers where applicable
- Keep commits atomic — one logical change per commit

## Submitting Changes

1. Ensure all tests pass
2. Update documentation if needed
3. Update `CHANGELOG.md` with your changes
4. Push to your fork and open a Pull Request
5. Describe your changes clearly in the PR description

## Reporting Issues

- Use GitHub Issues
- Include steps to reproduce
- Include relevant logs and system information

## Code of Conduct

Be respectful and constructive. We are building something useful together.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
