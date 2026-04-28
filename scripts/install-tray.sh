#!/bin/bash
# =============================================================================
# install-tray.sh — Install Captivity System Tray Autostart
# Part of the Captivity project (https://github.com/gaminization/captivity)
# Version: v1.1
#
# Installs the captivity-tray.desktop file to the XDG autostart directory
# so the tray icon launches automatically on login.
#
# Usage:
#   ./install-tray.sh [--uninstall]
# =============================================================================

set -euo pipefail

readonly PROG="captivity-install-tray"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly DESKTOP_SRC="${PROJECT_DIR}/systemd/captivity-tray.desktop"
readonly AUTOSTART_DIR="${HOME}/.config/autostart"
readonly DESKTOP_DEST="${AUTOSTART_DIR}/captivity-tray.desktop"

log_info()  { echo "[${PROG}] $*"; }
log_error() { echo "[${PROG}] ERROR: $*" >&2; }

# --- Install -----------------------------------------------------------------
do_install() {
    # Verify source exists
    if [[ ! -f "${DESKTOP_SRC}" ]]; then
        log_error "Desktop file not found: ${DESKTOP_SRC}"
        exit 1
    fi

    # Verify captivity CLI is available
    if ! command -v captivity &>/dev/null; then
        log_error "captivity CLI not found in PATH."
        log_error "Install it first: pip install -e ."
        exit 1
    fi

    # Create autostart directory
    mkdir -p "${AUTOSTART_DIR}"

    # Install desktop file
    cp "${DESKTOP_SRC}" "${DESKTOP_DEST}"
    log_info "Installed tray autostart to ${DESKTOP_DEST}"
    log_info "The tray icon will launch automatically on next login."
    log_info "To start it now: captivity tray &"
}

# --- Uninstall ---------------------------------------------------------------
do_uninstall() {
    if [[ -f "${DESKTOP_DEST}" ]]; then
        rm -f "${DESKTOP_DEST}"
        log_info "Removed ${DESKTOP_DEST}"
    else
        log_info "Autostart file not found (already removed?)."
    fi
}

# --- Main --------------------------------------------------------------------
main() {
    case "${1:-}" in
        --uninstall)
            do_uninstall
            ;;
        --help|-h)
            echo "Usage: $0 [--uninstall]"
            echo ""
            echo "Install the Captivity tray icon autostart entry."
            echo "Use --uninstall to remove it."
            ;;
        "")
            do_install
            ;;
        *)
            log_error "Unknown argument: $1"
            echo "Usage: $0 [--uninstall]"
            exit 1
            ;;
    esac
}

main "$@"
