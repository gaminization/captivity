# Contributing to Captivity

Thank you for your interest in contributing to Captivity!

## Getting Started

1. Fork the repository

2. Clone your fork:

   ```bash
   git clone https://github.com/<your-username>/captivity.git
   cd captivity
   ```

3. Create a feature branch from `dev`:

   ```bash
   git checkout dev
   git checkout -b feature/your-feature-name
   ```

## Branch Strategy

| Branch         | Purpose                                        |
| -------------- | ---------------------------------------------- |
| `main` | Stable releases only — always production-ready |
| `dev` | Active development — all feature branches merge here |
| `release/vX.X` | Temporary staging for release preparation |

### Workflow

```text
feature/your-feature  →  dev  →  release/vX.X  →  main
```

1. Create a feature branch from `dev`
2. Open a PR targeting `dev`
3. When preparing a release, cut a `release/vX.X` branch from `dev`
4. After final testing, merge `release/vX.X` into `main` and tag it

## Commit Conventions

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

### Feature Commits

```text
feat: add circuit breaker to retry engine
fix: resolve DNS timeout on reconnect
refactor: extract portal parser into separate module
docs: update CLI usage examples
test: add bandwidth monitor edge case tests
chore: update .gitignore for Rust build artifacts
```

### Release Commits

```text
release: vX.X <feature summary>
```

Example: `release: v1.5 Smart retry system`

### Rules

- Use **lowercase** for the type prefix
- Use **imperative mood** in the description (e.g., "add", not "added")
- Keep the subject line under 72 characters
- Reference issue numbers where applicable: `feat: add retry (#42)`

## Development Guidelines

### Code Style

- **Shell scripts**: Use `set -euo pipefail`, quote all variables, use `readonly` for constants
- **Python**: Follow PEP 8, use type hints where practical
- **Rust**: Run `cargo fmt` and `cargo clippy` before committing
- **Functions**: Use descriptive names with `snake_case`
- **Comments**: Add a file header explaining purpose and usage

### Testing

- All code must have corresponding tests
- Python tests use `pytest`, shell tests produce TAP-compatible output
- Run all tests before submitting:
  ```bash
  # Python tests
  PYTHONPATH=src python3 -m pytest tests/python/ -v

  # Shell tests
  for f in tests/test_*.sh; do bash "$f"; done

  # Rust tests
  cd daemon-rs && cargo test
  ```

## Release Process

1. Create a `release/vX.X` branch from `dev`
2. Update version in `pyproject.toml`
3. Update `CHANGELOG.md` with new version section
4. Merge into `main` via PR

5. Create an annotated tag:

   ```bash
   git tag -a vX.X -m "Captivity vX.X — Feature Summary"
   ```

6. Push the tag: `git push origin vX.X`
7. Create a GitHub Release from the tag

## Submitting Changes

1. Ensure all tests pass
2. Update documentation if needed
3. Update `CHANGELOG.md` with your changes
4. Push to your fork and open a Pull Request targeting `dev`
5. Describe your changes clearly in the PR description

## Reporting Issues

- Use GitHub Issues
- Include steps to reproduce
- Include relevant logs and system information

## Code of Conduct

Be respectful and constructive. We are building something useful together.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
