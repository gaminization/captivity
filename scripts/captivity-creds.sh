#!/bin/bash
# =============================================================================
# captivity-creds.sh — Credential Management for Captivity
# Part of the Captivity project (https://github.com/gaminization/captivity)
# Version: v0.2
#
# Manages WiFi captive portal credentials using Linux Secret Service
# via the secret-tool CLI utility.
#
# Usage:
#   captivity-creds.sh store <network>      Store credentials for a network
#   captivity-creds.sh retrieve <network>   Retrieve credentials for a network
#   captivity-creds.sh delete <network>     Delete credentials for a network
#   captivity-creds.sh list                 List stored network names
#
# Dependencies: secret-tool (libsecret-tools)
# =============================================================================

set -euo pipefail

# --- Constants ---------------------------------------------------------------
readonly PROG="captivity-creds"
readonly ATTR_APP="application"
readonly ATTR_APP_VAL="captivity"
readonly ATTR_NETWORK="network"
readonly ATTR_FIELD="field"

# --- Logging -----------------------------------------------------------------
log_info()  { echo "[${PROG}] $*"; }
log_error() { echo "[${PROG}] ERROR: $*" >&2; }

# --- Dependency Check --------------------------------------------------------
check_secret_tool() {
    if ! command -v secret-tool &>/dev/null; then
        log_error "secret-tool not found. Install libsecret-tools:"
        log_error "  sudo apt install libsecret-tools    # Debian/Ubuntu"
        log_error "  sudo dnf install libsecret           # Fedora"
        log_error "  sudo pacman -S libsecret             # Arch"
        return 1
    fi
}

# --- Usage -------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 <command> [<network>]

Commands:
  store <network>       Store username and password for a network
  retrieve <network>    Retrieve stored credentials for a network
  delete <network>      Delete stored credentials for a network
  list                  List networks with stored credentials

Options:
  -h, --help            Show this help message

Examples:
  $0 store campus_wifi
  $0 retrieve campus_wifi
  $0 delete campus_wifi
  $0 list
EOF
}

# --- Store Credentials -------------------------------------------------------
cmd_store() {
    local network="$1"

    log_info "Storing credentials for network: ${network}"

    # Read username
    read -rp "Username: " username
    if [[ -z "${username}" ]]; then
        log_error "Username cannot be empty."
        return 1
    fi

    # Read password (hidden)
    read -rsp "Password: " password
    echo
    if [[ -z "${password}" ]]; then
        log_error "Password cannot be empty."
        return 1
    fi

    # Store username
    echo -n "${username}" | secret-tool store --label="captivity-${network}-username" \
        "${ATTR_APP}" "${ATTR_APP_VAL}" \
        "${ATTR_NETWORK}" "${network}" \
        "${ATTR_FIELD}" "username"

    # Store password
    echo -n "${password}" | secret-tool store --label="captivity-${network}-password" \
        "${ATTR_APP}" "${ATTR_APP_VAL}" \
        "${ATTR_NETWORK}" "${network}" \
        "${ATTR_FIELD}" "password"

    log_info "Credentials stored successfully for '${network}'."
}

# --- Retrieve Credentials ----------------------------------------------------
cmd_retrieve() {
    local network="$1"

    local username password

    username=$(secret-tool lookup \
        "${ATTR_APP}" "${ATTR_APP_VAL}" \
        "${ATTR_NETWORK}" "${network}" \
        "${ATTR_FIELD}" "username" 2>/dev/null) || true

    password=$(secret-tool lookup \
        "${ATTR_APP}" "${ATTR_APP_VAL}" \
        "${ATTR_NETWORK}" "${network}" \
        "${ATTR_FIELD}" "password" 2>/dev/null) || true

    if [[ -z "${username}" && -z "${password}" ]]; then
        log_error "No credentials found for network '${network}'."
        return 1
    fi

    echo "username=${username}"
    echo "password=${password}"
}

# --- Delete Credentials ------------------------------------------------------
cmd_delete() {
    local network="$1"

    log_info "Deleting credentials for network: ${network}"

    secret-tool clear \
        "${ATTR_APP}" "${ATTR_APP_VAL}" \
        "${ATTR_NETWORK}" "${network}" \
        "${ATTR_FIELD}" "username" 2>/dev/null || true

    secret-tool clear \
        "${ATTR_APP}" "${ATTR_APP_VAL}" \
        "${ATTR_NETWORK}" "${network}" \
        "${ATTR_FIELD}" "password" 2>/dev/null || true

    log_info "Credentials deleted for '${network}'."
}

# --- List Networks -----------------------------------------------------------
cmd_list() {
    log_info "Stored networks:"

    # Search for all captivity entries and extract unique network names
    local networks
    networks=$(secret-tool search --all \
        "${ATTR_APP}" "${ATTR_APP_VAL}" 2>/dev/null \
        | grep "attribute.${ATTR_NETWORK}" \
        | sed 's/.*= //' \
        | sort -u) || true

    if [[ -z "${networks}" ]]; then
        echo "  (none)"
    else
        echo "${networks}" | while read -r net; do
            echo "  - ${net}"
        done
    fi
}

# --- Main --------------------------------------------------------------------
main() {
    if [[ $# -lt 1 ]]; then
        usage
        exit 1
    fi

    local command="$1"
    shift

    case "${command}" in
        -h|--help)
            usage
            exit 0
            ;;
        store|retrieve|delete)
            if [[ $# -lt 1 ]]; then
                log_error "'${command}' requires a <network> argument."
                usage
                exit 1
            fi
            check_secret_tool || exit 1
            "cmd_${command}" "$1"
            ;;
        list)
            check_secret_tool || exit 1
            cmd_list
            ;;
        *)
            log_error "Unknown command: ${command}"
            usage
            exit 1
            ;;
    esac
}

main "$@"
