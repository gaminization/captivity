#!/bin/bash
# =============================================================================
# install-dispatcher.sh — Install Captivity NetworkManager Dispatcher
# Part of the Captivity project (https://github.com/gaminization/captivity)
# Version: v0.4
#
# Installs the captivity-dispatcher.sh script into NetworkManager's
# dispatcher directory. Requires root privileges.
#
# Usage:
#   sudo ./install-dispatcher.sh [--uninstall]
# =============================================================================

set -euo pipefail

readonly PROG="captivity-install-dispatcher"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly DISPATCHER_SRC="${SCRIPT_DIR}/captivity-dispatcher.sh"
readonly DISPATCHER_DEST="/etc/NetworkManager/dispatcher.d/90-captivity"
readonly CONFIG_DIR="/etc/captivity"
readonly CONFIG_FILE="${CONFIG_DIR}/config"
readonly INSTALL_DIR="/opt/captivity"

log_info()  { echo "[${PROG}] $*"; }
log_error() { echo "[${PROG}] ERROR: $*" >&2; }

# --- Root Check --------------------------------------------------------------
check_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        log_error "This script must be run as root (sudo)."
        exit 1
    fi
}

# --- Install -----------------------------------------------------------------
do_install() {
    check_root

    log_info "Installing Captivity dispatcher..."

    # Create installation directory
    if [[ ! -d "${INSTALL_DIR}" ]]; then
        log_info "Creating ${INSTALL_DIR}..."
        mkdir -p "${INSTALL_DIR}/scripts"
        cp -r "${PROJECT_DIR}/scripts/"* "${INSTALL_DIR}/scripts/"
        chmod +x "${INSTALL_DIR}/scripts/"*.sh
    fi

    # Install dispatcher
    if [[ ! -d "$(dirname "${DISPATCHER_DEST}")" ]]; then
        log_error "NetworkManager dispatcher directory not found."
        log_error "Is NetworkManager installed?"
        exit 1
    fi

    log_info "Installing dispatcher to ${DISPATCHER_DEST}..."
    cp "${DISPATCHER_SRC}" "${DISPATCHER_DEST}"
    chmod 755 "${DISPATCHER_DEST}"

    # Create config directory and template
    if [[ ! -d "${CONFIG_DIR}" ]]; then
        log_info "Creating config directory ${CONFIG_DIR}..."
        mkdir -p "${CONFIG_DIR}"
    fi

    if [[ ! -f "${CONFIG_FILE}" ]]; then
        log_info "Creating config template at ${CONFIG_FILE}..."
        cat > "${CONFIG_FILE}" <<'EOF'
# Captivity Configuration
# =======================
# Network name for credential lookup
# CAPTIVITY_NETWORK="my_campus_wifi"

# Portal URL (optional, auto-detected if empty)
# CAPTIVITY_PORTAL="http://portal.example.com/login"

# Installation directory
CAPTIVITY_DIR="/opt/captivity"
EOF
        chmod 644 "${CONFIG_FILE}"
    fi

    log_info "Installation complete!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Edit ${CONFIG_FILE} with your network settings"
    log_info "  2. Store credentials: ${INSTALL_DIR}/scripts/captivity-creds.sh store <network>"
    log_info "  3. Test: ${DISPATCHER_DEST} wlan0 up"
}

# --- Uninstall ---------------------------------------------------------------
do_uninstall() {
    check_root

    log_info "Uninstalling Captivity dispatcher..."

    if [[ -f "${DISPATCHER_DEST}" ]]; then
        rm -f "${DISPATCHER_DEST}"
        log_info "Removed ${DISPATCHER_DEST}"
    else
        log_info "Dispatcher not found at ${DISPATCHER_DEST} (already removed?)"
    fi

    log_info "Uninstallation complete."
    log_info "Note: ${CONFIG_DIR} and ${INSTALL_DIR} were NOT removed."
    log_info "Remove them manually if desired."
}

# --- Main --------------------------------------------------------------------
main() {
    case "${1:-}" in
        --uninstall)
            do_uninstall
            ;;
        --help|-h)
            echo "Usage: sudo $0 [--uninstall]"
            echo ""
            echo "Install the Captivity NetworkManager dispatcher hook."
            echo "Use --uninstall to remove it."
            ;;
        "")
            do_install
            ;;
        *)
            log_error "Unknown argument: $1"
            echo "Usage: sudo $0 [--uninstall]"
            exit 1
            ;;
    esac
}

main "$@"
