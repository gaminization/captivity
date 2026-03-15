#!/bin/bash
# =============================================================================
# captivity-reconnect.sh — Automatic Reconnect Loop for Captivity
# Part of the Captivity project (https://github.com/gaminization/captivity)
# Version: v0.3
#
# Monitors internet connectivity via lightweight HTTP probes.
# When a captive portal is detected, triggers automatic login.
# Supports exponential backoff retry and graceful shutdown.
#
# Usage:
#   captivity-reconnect.sh [--network <SSID>] [--portal <URL>] [--interval <sec>]
#                          [--once] [--daemon] [--dry-run]
#
# Dependencies: curl, scripts/captivity-login.sh
# =============================================================================

set -euo pipefail

# --- Constants ---------------------------------------------------------------
readonly PROG="captivity-reconnect"
readonly PROBE_URL="https://clients3.google.com/generate_204"
readonly PROBE_TIMEOUT=5
readonly DEFAULT_INTERVAL=30
readonly BACKOFF_INTERVALS=(5 10 30 60 120 300)
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOGIN_SCRIPT="${SCRIPT_DIR}/captivity-login.sh"

# --- Defaults ----------------------------------------------------------------
NETWORK=""
PORTAL=""
INTERVAL="${DEFAULT_INTERVAL}"
RUN_ONCE=false
DAEMON_MODE=false
DRY_RUN=false
SHOULD_RUN=true
CONSECUTIVE_FAILURES=0

# --- Logging -----------------------------------------------------------------
log_ts() {
    date '+%Y-%m-%d %H:%M:%S'
}

log_info() {
    echo "[$(log_ts)] [${PROG}] INFO: $*"
}

log_warn() {
    echo "[$(log_ts)] [${PROG}] WARN: $*" >&2
}

log_error() {
    echo "[$(log_ts)] [${PROG}] ERROR: $*" >&2
}

log_debug() {
    [[ "${CAPTIVITY_DEBUG:-0}" == "1" ]] && echo "[$(log_ts)] [${PROG}] DEBUG: $*" || true
}

# --- Signal Handling ---------------------------------------------------------
handle_signal() {
    log_info "Received shutdown signal. Exiting gracefully..."
    SHOULD_RUN=false
}

trap handle_signal SIGTERM SIGINT

# --- Usage -------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 [options]

Monitors connectivity and automatically logs into captive portals.

Options:
  --network <SSID>    Network name for credential lookup
  --portal <URL>      Portal login URL
  --interval <sec>    Probe interval in seconds (default: ${DEFAULT_INTERVAL})
  --once              Run a single connectivity probe and exit
  --daemon            Run in continuous daemon mode with structured logging
  --dry-run           Print actions without executing them
  -h, --help          Show this help message

Probe Behavior:
  HTTP 204            → Internet available (connected)
  HTTP redirect/other → Captive portal detected (triggers login)
  Timeout/error       → Network unavailable (retry with backoff)

Examples:
  $0 --once                                    # Single probe
  $0 --network campus --interval 60            # Monitor every 60s
  $0 --network campus --portal http://... --daemon
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
            --interval)
                INTERVAL="$2"
                shift 2
                ;;
            --once)
                RUN_ONCE=true
                shift
                ;;
            --daemon)
                DAEMON_MODE=true
                shift
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
}

# --- Connectivity Probe -----------------------------------------------------
# Returns:
#   0 = connected (HTTP 204)
#   1 = captive portal detected (redirect/HTML)
#   2 = network unavailable (timeout/error)
probe_connectivity() {
    if [[ "${DRY_RUN}" == true ]]; then
        echo "[DRY-RUN] curl -s -o /dev/null -w '%{http_code}' --max-time ${PROBE_TIMEOUT} ${PROBE_URL}"
        return 0
    fi

    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' \
        --max-time "${PROBE_TIMEOUT}" \
        "${PROBE_URL}" 2>/dev/null) || {
        log_debug "Probe failed (network error)"
        return 2
    }

    log_debug "Probe response: HTTP ${http_code}"

    case "${http_code}" in
        204)
            return 0
            ;;
        301|302|303|307|308)
            return 1
            ;;
        000)
            return 2
            ;;
        *)
            # Any other response (200 with HTML, etc.) likely indicates a portal
            return 1
            ;;
    esac
}

# --- Get Backoff Interval ----------------------------------------------------
get_backoff_interval() {
    local failures="$1"
    local max_index=$(( ${#BACKOFF_INTERVALS[@]} - 1 ))
    local index=$(( failures < max_index ? failures : max_index ))
    echo "${BACKOFF_INTERVALS[${index}]}"
}

# --- Trigger Login -----------------------------------------------------------
do_login() {
    log_info "Captive portal detected. Triggering login..."

    local login_args=()

    if [[ -n "${NETWORK}" ]]; then
        login_args+=(--network "${NETWORK}")
    fi

    if [[ -n "${PORTAL}" ]]; then
        login_args+=(--portal "${PORTAL}")
    fi

    if [[ "${DRY_RUN}" == true ]]; then
        login_args+=(--dry-run)
    fi

    if [[ ${#login_args[@]} -eq 0 || -z "${NETWORK}" ]]; then
        log_error "Cannot login: --network not specified."
        return 1
    fi

    if [[ ! -x "${LOGIN_SCRIPT}" ]]; then
        log_error "Login script not found: ${LOGIN_SCRIPT}"
        return 1
    fi

    if "${LOGIN_SCRIPT}" "${login_args[@]}"; then
        log_info "Login completed successfully."
        CONSECUTIVE_FAILURES=0
        return 0
    else
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        local backoff
        backoff=$(get_backoff_interval "${CONSECUTIVE_FAILURES}")
        log_warn "Login failed (attempt ${CONSECUTIVE_FAILURES}). Next retry in ${backoff}s."
        return 1
    fi
}

# --- Single Probe ------------------------------------------------------------
run_once() {
    log_info "Running single connectivity probe..."

    probe_connectivity
    local result=$?

    case ${result} in
        0)
            log_info "Status: CONNECTED (HTTP 204)"
            return 0
            ;;
        1)
            log_info "Status: CAPTIVE PORTAL DETECTED"
            if [[ -n "${NETWORK}" ]]; then
                do_login
                return $?
            else
                log_info "No --network specified. Skipping auto-login."
                return 1
            fi
            ;;
        2)
            log_info "Status: NETWORK UNAVAILABLE"
            return 2
            ;;
    esac
}

# --- Reconnect Loop ----------------------------------------------------------
run_loop() {
    log_info "Starting reconnect loop (interval: ${INTERVAL}s)"
    [[ -n "${NETWORK}" ]] && log_info "Network: ${NETWORK}"
    [[ -n "${PORTAL}" ]] && log_info "Portal:  ${PORTAL}"
    [[ "${DAEMON_MODE}" == true ]] && log_info "Mode:    DAEMON"

    while [[ "${SHOULD_RUN}" == true ]]; do
        probe_connectivity
        local result=$?

        case ${result} in
            0)
                log_debug "Connected. Next probe in ${INTERVAL}s."
                CONSECUTIVE_FAILURES=0
                ;;
            1)
                do_login || true
                ;;
            2)
                CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
                local backoff
                backoff=$(get_backoff_interval "${CONSECUTIVE_FAILURES}")
                log_warn "Network unavailable (${CONSECUTIVE_FAILURES} failures). Retry in ${backoff}s."
                sleep_interruptible "${backoff}"
                continue
                ;;
        esac

        sleep_interruptible "${INTERVAL}"
    done

    log_info "Reconnect loop stopped."
}

# --- Interruptible Sleep -----------------------------------------------------
sleep_interruptible() {
    local duration="$1"
    local elapsed=0
    while [[ ${elapsed} -lt ${duration} && "${SHOULD_RUN}" == true ]]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done
}

# --- Main --------------------------------------------------------------------
main() {
    parse_args "$@"

    if [[ "${RUN_ONCE}" == true ]]; then
        run_once
        exit $?
    fi

    run_loop
}

main "$@"
