#!/bin/bash
# =============================================================================
# install-service.sh — Install Captivity Systemd Service
# Part of the Captivity project (https://github.com/gaminization/captivity)
# Version: v0.5
#
# Installs the captivity systemd service unit for auto-start on boot.
# Requires root privileges.
#
# Usage:
#   sudo ./install-service.sh [--uninstall] [--enable] [--start]
# =============================================================================

set -euo pipefail

readonly PROG="captivity-install-service"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SERVICE_SRC="${PROJECT_DIR}/systemd/captivity.service"
readonly SERVICE_DEST="/etc/systemd/system/captivity.service"
readonly INSTALL_DIR="/opt/captivity"
readonly CONFIG_DIR="/etc/captivity"
readonly CONFIG_FILE="${CONFIG_DIR}/config"

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

    log_info "Installing Captivity systemd service..."

    # Ensure scripts are installed
    if [[ ! -d "${INSTALL_DIR}/scripts" ]]; then
        log_info "Installing scripts to ${INSTALL_DIR}..."
        mkdir -p "${INSTALL_DIR}/scripts"
        cp -r "${PROJECT_DIR}/scripts/"* "${INSTALL_DIR}/scripts/"
        chmod +x "${INSTALL_DIR}/scripts/"*.sh
    fi

    # Ensure config directory exists
    if [[ ! -d "${CONFIG_DIR}" ]]; then
        mkdir -p "${CONFIG_DIR}"
    fi

    # Create config file if missing
    if [[ ! -f "${CONFIG_FILE}" ]]; then
        log_info "Creating config at ${CONFIG_FILE}..."
        cat > "${CONFIG_FILE}" <<'EOF'
# Captivity Configuration
# =======================
# Network name for credential lookup (required)
# CAPTIVITY_NETWORK="my_campus_wifi"

# Portal URL (optional, auto-detected if empty)
# CAPTIVITY_PORTAL=""

# Installation directory
CAPTIVITY_DIR="/opt/captivity"
EOF
        chmod 644 "${CONFIG_FILE}"
    fi

    # Install service file
    if [[ ! -f "${SERVICE_SRC}" ]]; then
        log_error "Service file not found: ${SERVICE_SRC}"
        exit 1
    fi

    log_info "Installing service to ${SERVICE_DEST}..."
    cp "${SERVICE_SRC}" "${SERVICE_DEST}"
    chmod 644 "${SERVICE_DEST}"

    # Reload systemd
    systemctl daemon-reload

    log_info "Service installed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Edit ${CONFIG_FILE} with your network settings"
    log_info "  2. Store credentials: ${INSTALL_DIR}/scripts/captivity-creds.sh store <network>"
    log_info "  3. Enable service:    sudo systemctl enable captivity"
    log_info "  4. Start service:     sudo systemctl start captivity"
    log_info "  5. Check status:      sudo systemctl status captivity"
    log_info "  6. View logs:         journalctl -u captivity -f"
}

# --- Enable/Start Helpers ----------------------------------------------------
do_enable() {
    check_root
    systemctl enable captivity
    log_info "Service enabled (will start on boot)."
}

do_start() {
    check_root
    systemctl start captivity
    log_info "Service started."
}

# --- Uninstall ---------------------------------------------------------------
do_uninstall() {
    check_root

    log_info "Uninstalling Captivity systemd service..."

    # Stop and disable if running
    systemctl stop captivity 2>/dev/null || true
    systemctl disable captivity 2>/dev/null || true

    if [[ -f "${SERVICE_DEST}" ]]; then
        rm -f "${SERVICE_DEST}"
        systemctl daemon-reload
        log_info "Service removed."
    else
        log_info "Service not found (already removed?)."
    fi

    log_info "Note: ${CONFIG_DIR} and ${INSTALL_DIR} were NOT removed."
}

# --- Usage -------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: sudo $0 [options]

Options:
  (no args)        Install the captivity systemd service
  --enable         Enable the service (auto-start on boot)
  --start          Start the service now
  --uninstall      Remove the service
  -h, --help       Show this help message

Examples:
  sudo $0                    # Install only
  sudo $0 --enable --start   # Install, enable, and start
  sudo $0 --uninstall        # Remove the service
EOF
}

# --- Main --------------------------------------------------------------------
main() {
    local do_install_flag=true
    local do_enable_flag=false
    local do_start_flag=false
    local do_uninstall_flag=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --enable)
                do_enable_flag=true
                shift
                ;;
            --start)
                do_start_flag=true
                shift
                ;;
            --uninstall)
                do_uninstall_flag=true
                do_install_flag=false
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown argument: $1"
                usage
                exit 1
                ;;
        esac
    done

    if [[ "${do_uninstall_flag}" == true ]]; then
        do_uninstall
    elif [[ "${do_install_flag}" == true ]]; then
        do_install
        [[ "${do_enable_flag}" == true ]] && do_enable
        [[ "${do_start_flag}" == true ]] && do_start
    fi
}

main "$@"
