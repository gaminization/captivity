#!/bin/bash
# =============================================================================
# captivity-login.sh — Enhanced Captive Portal Login for Captivity
# Part of the Captivity project (https://github.com/gaminization/captivity)
# Version: v0.2
#
# Logs into a captive portal using credentials stored securely via
# secret-tool (Linux Secret Service). Preserves the same Pronto Networks
# curl-based login logic from the original login.sh.
#
# Usage:
#   captivity-login.sh --network <SSID> [--portal <URL>] [--dry-run]
#
# Options:
#   --network <SSID>    Network name for credential lookup (required)
#   --portal <URL>      Portal login URL (default: Pronto Networks)
#   --dry-run           Print the curl command without executing it
#   -h, --help          Show help
#
# Dependencies: curl, secret-tool (libsecret-tools)
# =============================================================================

set -euo pipefail

# --- Constants ---------------------------------------------------------------
readonly PROG="captivity-login"
readonly DEFAULT_PORTAL="http://phc.prontonetworks.com/cgi-bin/authlogin"
readonly COOKIE_FILE="/tmp/captivity_cookie_$$"
readonly CONNECTIVITY_URL="https://clients3.google.com/generate_204"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Defaults ----------------------------------------------------------------
NETWORK=""
PORTAL="${DEFAULT_PORTAL}"
DRY_RUN=false

# --- Logging -----------------------------------------------------------------
log_info()  { echo "[${PROG}] $*"; }
log_error() { echo "[${PROG}] ERROR: $*" >&2; }
log_debug() { [[ "${CAPTIVITY_DEBUG:-0}" == "1" ]] && echo "[${PROG}] DEBUG: $*" || true; }

# --- Cleanup -----------------------------------------------------------------
cleanup() {
    rm -f "${COOKIE_FILE}" 2>/dev/null || true
}
trap cleanup EXIT

# --- Usage -------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 --network <SSID> [--portal <URL>] [--dry-run]

Options:
  --network <SSID>    Network name for credential lookup (required)
  --portal <URL>      Portal login URL (default: Pronto Networks endpoint)
  --dry-run           Print the curl commands without executing them
  -h, --help          Show this help message

Examples:
  $0 --network campus_wifi
  $0 --network campus_wifi --portal http://portal.example.com/login
  $0 --network campus_wifi --dry-run
EOF
}

# --- Parse Arguments ---------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --network)
                NETWORK="$2"
                shift 2
                ;;
            --portal)
                PORTAL="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
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

    if [[ -z "${NETWORK}" ]]; then
        log_error "Missing required argument: --network <SSID>"
        usage
        exit 1
    fi
}

# --- Credential Retrieval ----------------------------------------------------
get_credentials() {
    local network="$1"

    log_debug "Retrieving credentials for network: ${network}"

    # Try secure retrieval via captivity-creds.sh
    if [[ -x "${SCRIPT_DIR}/captivity-creds.sh" ]]; then
        local creds_output
        creds_output=$("${SCRIPT_DIR}/captivity-creds.sh" retrieve "${network}" 2>/dev/null) || {
            log_error "Failed to retrieve credentials for '${network}'."
            log_error "Store them first:  captivity-creds.sh store ${network}"
            return 1
        }

        USERNAME=$(echo "${creds_output}" | grep '^username=' | cut -d= -f2-)
        PASSWORD=$(echo "${creds_output}" | grep '^password=' | cut -d= -f2-)

        if [[ -z "${USERNAME}" || -z "${PASSWORD}" ]]; then
            log_error "Incomplete credentials for '${network}'."
            return 1
        fi

        log_debug "Credentials retrieved successfully."
    else
        log_error "captivity-creds.sh not found at ${SCRIPT_DIR}/captivity-creds.sh"
        log_error "Cannot retrieve credentials without the credential manager."
        return 1
    fi
}

# --- Portal Login ------------------------------------------------------------
do_login() {
    local username="$1"
    local password="$2"
    local portal="$3"

    log_info "Triggering captive portal at ${portal}..."

    if [[ "${DRY_RUN}" == true ]]; then
        echo "[DRY-RUN] curl -s -c ${COOKIE_FILE} \"${portal}\""
        echo "[DRY-RUN] curl -s -b ${COOKIE_FILE} -c ${COOKIE_FILE} \\"
        echo "  -d \"userId=<USERNAME>\" \\"
        echo "  -d \"password=<PASSWORD>\" \\"
        echo "  -d \"serviceName=ProntoAuthentication\" \\"
        echo "  -d \"Submit22=Login\" \\"
        echo "  \"${portal}\""
        return 0
    fi

    # Step 1: Trigger the portal (get cookies)
    curl -s -c "${COOKIE_FILE}" "${portal}" > /dev/null

    log_info "Logging in as ${username}..."

    # Step 2: Submit login (same logic as original login.sh)
    curl -s -b "${COOKIE_FILE}" -c "${COOKIE_FILE}" \
        -d "userId=${username}" \
        -d "password=${password}" \
        -d "serviceName=ProntoAuthentication" \
        -d "Submit22=Login" \
        "${portal}" > /dev/null
}

# --- Connectivity Check ------------------------------------------------------
check_connectivity() {
    log_info "Checking internet connectivity..."

    if [[ "${DRY_RUN}" == true ]]; then
        echo "[DRY-RUN] curl -s --max-time 5 ${CONNECTIVITY_URL}"
        echo "[DRY-RUN] Connectivity check skipped."
        return 0
    fi

    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${CONNECTIVITY_URL}" 2>/dev/null) || true

    if [[ "${http_code}" == "204" ]]; then
        log_info "WiFi login successful! (HTTP ${http_code})"
        return 0
    else
        log_error "Login may have failed. (HTTP ${http_code:-timeout})"
        return 1
    fi
}

# --- Main --------------------------------------------------------------------
main() {
    parse_args "$@"

    log_info "Network: ${NETWORK}"
    log_info "Portal:  ${PORTAL}"
    [[ "${DRY_RUN}" == true ]] && log_info "Mode:    DRY-RUN"

    get_credentials "${NETWORK}"
    do_login "${USERNAME}" "${PASSWORD}" "${PORTAL}"
    check_connectivity
}

main "$@"
