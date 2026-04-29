#!/usr/bin/env bash
# install-launchd.sh — Install Captivity as a macOS LaunchAgent
#
# Usage: ./scripts/install-launchd.sh
#
# Installs the plist to ~/Library/LaunchAgents and loads it via launchctl.
# Requires: macOS, captivity CLI installed and available on PATH.

set -euo pipefail

PLIST_NAME="com.gaminization.captivity.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_PLIST="$REPO_ROOT/launchd/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"

# --- Preflight checks ---

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "ERROR: This script is for macOS only." >&2
    exit 1
fi

if ! command -v captivity &>/dev/null; then
    echo "ERROR: 'captivity' CLI not found on PATH." >&2
    echo "       Install with: pip install -e ." >&2
    exit 1
fi

if [[ ! -f "$SOURCE_PLIST" ]]; then
    echo "ERROR: Source plist not found: $SOURCE_PLIST" >&2
    exit 1
fi

# --- Resolve captivity path into the plist ---

CAPTIVITY_PATH="$(command -v captivity)"
echo "Using captivity at: $CAPTIVITY_PATH"

# Create a temporary plist with the resolved path
TEMP_PLIST="$(mktemp)"
sed "s|/usr/local/bin/captivity|$CAPTIVITY_PATH|g" "$SOURCE_PLIST" > "$TEMP_PLIST"

# --- Unload existing (if any) ---

if launchctl list "$PLIST_NAME" &>/dev/null 2>&1; then
    echo "Unloading existing service..."
    launchctl unload "$TARGET_PLIST" 2>/dev/null || true
fi

# --- Install ---

mkdir -p "$TARGET_DIR"
cp "$TEMP_PLIST" "$TARGET_PLIST"
rm -f "$TEMP_PLIST"

echo "Installed plist to: $TARGET_PLIST"

# --- Load ---

launchctl load "$TARGET_PLIST"
echo "Service loaded. Captivity daemon is now running."
echo ""
echo "Management commands:"
echo "  launchctl stop  $PLIST_NAME    # Stop"
echo "  launchctl start $PLIST_NAME    # Start"
echo "  launchctl unload $TARGET_PLIST # Uninstall"
echo "  tail -f /tmp/captivity.out     # View logs"
