#!/usr/bin/env bash
# Generates the CLI documentation from the captivity --help output.
set -euo pipefail

cd "$(dirname "$0")/.."

DOC_FILE="docs/cli.md"

echo "# Captivity CLI Reference" > "$DOC_FILE"
echo "" >> "$DOC_FILE"
echo "\`\`\`text" >> "$DOC_FILE"
PYTHONPATH=src python3 -m captivity.cli --help >> "$DOC_FILE"
echo "\`\`\`" >> "$DOC_FILE"

echo "Generated $DOC_FILE"
