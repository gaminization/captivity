#!/bin/bash
# =============================================================================
# captivity-dispatcher.sh — NetworkManager Dispatcher Hook for Captivity
# Part of the Captivity project (https://github.com/gaminization/captivity)
# Version: v0.4
#
# NetworkManager dispatcher script that triggers automatic captive portal
# login when WiFi connects or connectivity changes.
#
# Install to: /etc/NetworkManager/dispatcher.d/90-captivity
#
# NetworkManager calls this script with:
#   $1 = interface name (e.g., wlan0, wlp2s0)
#   $2 = action (up, down, connectivity-change, etc.)
#
# Dependencies: scripts/captivity-login.sh, scripts/captivity-reconnect.sh
# =============================================================================

set -euo pipefail

# --- Constants ---------------------------------------------------------------
readonly PROG="captivity-dispatcher"
readonly CAPTIVITY_DIR="${CAPTIVITY_DIR:-/opt/captivity}"
readonly RECONNECT_SCRIPT="${CAPTIVITY_DIR}/scripts/captivity-reconnect.sh"
readonly LOG_TAG="captivity"

# --- Configuration -----------------------------------------------------------
# Network to auto-login (can be overridden via /etc/captivity/config)
CAPTIVITY_NETWORK="${CAPTIVITY_NETWORK:-}"
CAPTIVITY_PORTAL="${CAPTIVITY_PORTAL:-}"
CAPTIVITY_CONFIG="/etc/captivity/config"

# --- Logging -----------------------------------------------------------------
log_info() {
    logger -t "${LOG_TAG}" -p daemon.info "$*"
}

log_error() {
    logger -t "${LOG_TAG}" -p daemon.err "$*"
}

log_debug() {
    logger -t "${LOG_TAG}" -p daemon.debug "$*"
}

# --- Load Config -------------------------------------------------------------
load_config() {
    if [[ -f "${CAPTIVITY_CONFIG}" ]]; then
        # shellcheck source=/dev/null
        source "${CAPTIVITY_CONFIG}"
    fi
}

# --- Interface Check ---------------------------------------------------------
is_wifi_interface() {
    local iface="$1"

    # Check if the interface is a wireless interface
    if [[ -d "/sys/class/net/${iface}/wireless" ]]; then
        return 0
    fi

    # Fallback: check if interface name matches common WiFi patterns
    case "${iface}" in
        wlan*|wlp*|wlo*|wifi*)
            return 0
            ;;
    esac

    return 1
}

# --- Trigger Login -----------------------------------------------------------
trigger_login() {
    local iface="$1"
    local action="$2"

    log_info "WiFi event: ${iface} ${action}"

    # Small delay to allow network stack to settle
    sleep 2

    if [[ -x "${RECONNECT_SCRIPT}" ]]; then
        local args=(--once)

        if [[ -n "${CAPTIVITY_NETWORK}" ]]; then
            args+=(--network "${CAPTIVITY_NETWORK}")
        fi

        if [[ -n "${CAPTIVITY_PORTAL}" ]]; then
            args+=(--portal "${CAPTIVITY_PORTAL}")
        fi

        log_info "Running connectivity probe..."
        "${RECONNECT_SCRIPT}" "${args[@]}" 2>&1 | while read -r line; do
            log_info "${line}"
        done
    else
        log_error "Reconnect script not found: ${RECONNECT_SCRIPT}"
    fi
}

# --- Main --------------------------------------------------------------------
main() {
    local iface="${1:-}"
    local action="${2:-}"

    # Validate arguments
    if [[ -z "${iface}" || -z "${action}" ]]; then
        echo "Usage: $0 <interface> <action>"
        echo ""
        echo "This script is intended to be called by NetworkManager."
        echo "Install to: /etc/NetworkManager/dispatcher.d/90-captivity"
        exit 1
    fi

    # Only process WiFi interfaces
    if ! is_wifi_interface "${iface}"; then
        log_debug "Ignoring non-WiFi interface: ${iface}"
        exit 0
    fi

    # Load configuration
    load_config

    # Handle relevant actions
    case "${action}" in
        up)
            log_info "WiFi interface ${iface} came up"
            trigger_login "${iface}" "${action}"
            ;;
        connectivity-change)
            log_info "Connectivity changed on ${iface}"
            trigger_login "${iface}" "${action}"
            ;;
        down)
            log_info "WiFi interface ${iface} went down"
            ;;
        *)
            log_debug "Ignoring action '${action}' on ${iface}"
            ;;
    esac
}

main "$@"
