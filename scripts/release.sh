#!/usr/bin/env bash
# Automates the release process for Captivity

set -euo pipefail

cd "$(dirname "$0")/.."

if ! git diff-index --quiet HEAD --; then
    echo "Error: Working directory is not clean. Commit or stash changes first."
    exit 1
fi

VERSION=$(grep -E '^version = ' pyproject.toml | cut -d '"' -f 2)

echo "Preparing release for Captivity v$VERSION..."

echo "1. Running tests and coverage..."
PYTHONPATH=src pytest tests/python/ tests/integration/ --cov=captivity --cov-fail-under=80 -q

echo "2. Generating CLI documentation..."
./scripts/generate_docs.sh

echo "3. Checking if documentation drift is resolved..."
./scripts/check_docs_drift.sh

echo "4. Checking CHANGELOG.md for v$VERSION..."
if ! grep -q "v$VERSION" CHANGELOG.md; then
    echo "Error: v$VERSION not found in CHANGELOG.md."
    exit 1
fi

echo "All checks passed. Creating git tag..."

git add docs/cli.md pyproject.toml requirements.lock CHANGELOG.md || true
if ! git diff-index --quiet HEAD --; then
    git commit -m "release: v$VERSION"
fi

if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo "Warning: Tag v$VERSION already exists."
else
    git tag -a "v$VERSION" -m "Captivity v$VERSION release"
    echo "Tag v$VERSION created."
fi

echo "Done! Run 'git push origin main --tags' to push the release."
