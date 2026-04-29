#!/usr/bin/env bash
# Checks if the generated CLI documentation matches the actual CLI output.
set -euo pipefail

cd "$(dirname "$0")/.."

DOC_FILE="docs/cli.md"

if [ ! -f "$DOC_FILE" ]; then
    echo "Error: $DOC_FILE not found. Run scripts/generate_docs.sh first."
    exit 1
fi

TEMP_DOC=$(mktemp)

echo "# Captivity CLI Reference" > "$TEMP_DOC"
echo "" >> "$TEMP_DOC"
echo "\`\`\`text" >> "$TEMP_DOC"
PYTHONPATH=src python3 -m captivity.cli --help >> "$TEMP_DOC"
echo "\`\`\`" >> "$TEMP_DOC"

if ! cmp -s "$DOC_FILE" "$TEMP_DOC"; then
    echo "Error: CLI documentation drift detected!"
    echo "The output of 'captivity --help' does not match $DOC_FILE."
    echo "Please run './scripts/generate_docs.sh' and commit the changes."
    rm -f "$TEMP_DOC"
    exit 1
fi

rm -f "$TEMP_DOC"
echo "CLI documentation is up-to-date."
