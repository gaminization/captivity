#!/bin/bash
# =============================================================================
# test_real_portal.sh — End-to-End Real Portal Test
# Part of the Captivity project
# Version: v2.1
#
# Tests the full captive portal detection and login flow on a real
# network. Designed for T-VIT or any CAPTCHA-based captive portal.
#
# Usage:
#   ./scripts/test_real_portal.sh [--network SSID]
#
# Requirements:
#   - NetworkManager installed
#   - captivity CLI installed
#   - WiFi adapter available
# =============================================================================

set -euo pipefail

readonly PROG="test_real_portal"
readonly NETWORK="${1:-T-VIT}"
readonly LOG_DIR="/tmp/captivity-test-$(date +%Y%m%d_%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

passed=0
failed=0
skipped=0

log_info()  { echo -e "${CYAN}[${PROG}]${NC} $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC} $*"; ((passed++)); }
log_fail()  { echo -e "${RED}[FAIL]${NC} $*"; ((failed++)); }
log_skip()  { echo -e "${YELLOW}[SKIP]${NC} $*"; ((skipped++)); }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }

# --- Setup -------------------------------------------------------------------
setup() {
    mkdir -p "${LOG_DIR}"
    log_info "Test logs: ${LOG_DIR}"
    log_info "Target network: ${NETWORK}"
    echo ""
}

# --- Test 1: CLI available ---------------------------------------------------
test_cli_available() {
    log_info "Test 1: CLI available"
    if command -v captivity &>/dev/null; then
        local version
        version=$(captivity --version 2>/dev/null || echo "unknown")
        log_pass "captivity CLI found: ${version}"
    else
        log_fail "captivity CLI not found in PATH"
        exit 1
    fi
}

# --- Test 2: Connect to network ---------------------------------------------
test_connect_network() {
    log_info "Test 2: Connect to ${NETWORK}"

    # Check if already connected to target
    local current_ssid
    current_ssid=$(nmcli -t -f active,ssid dev wifi | grep '^yes:' | cut -d: -f2 || true)

    if [[ "${current_ssid}" == "${NETWORK}" ]]; then
        log_info "Already connected to ${NETWORK}"
        log_pass "Network connection: ${NETWORK}"
        return
    fi

    # Scan for network
    log_info "Scanning for ${NETWORK}..."
    nmcli device wifi rescan 2>/dev/null || true
    sleep 2

    if nmcli device wifi list | grep -q "${NETWORK}"; then
        log_info "Found ${NETWORK}, connecting..."
        if nmcli device wifi connect "${NETWORK}" 2>&1 | tee "${LOG_DIR}/connect.log"; then
            log_pass "Connected to ${NETWORK}"
        else
            log_fail "Failed to connect to ${NETWORK}"
            return
        fi
    else
        log_skip "Network '${NETWORK}' not found in WiFi scan"
    fi
}

# --- Test 3: Verify portal is active ----------------------------------------
test_portal_active() {
    log_info "Test 3: Verify captive portal is active"

    # ping should fail or DNS should redirect
    if ping -c 1 -W 3 google.com &>/dev/null; then
        log_warn "ping to google.com succeeded — may already be logged in"
        log_skip "Portal may not be active"
        return
    fi

    log_pass "ping failed — captive portal likely active"
}

# --- Test 4: Probe detects portal -------------------------------------------
test_probe_detection() {
    log_info "Test 4: Probe detects captive portal"

    local probe_output
    probe_output=$(captivity probe 2>&1)
    echo "${probe_output}" > "${LOG_DIR}/probe.log"

    echo "${probe_output}"

    if echo "${probe_output}" | grep -q "portal_detected"; then
        log_pass "Probe correctly detected portal"
    elif echo "${probe_output}" | grep -q "connected"; then
        log_warn "Probe reports connected — portal may not be active"
        log_skip "Probe shows connected (expected portal)"
    else
        log_fail "Probe did not detect portal"
    fi
}

# --- Test 5: Check CAPTCHA detection ----------------------------------------
test_captcha_detection() {
    log_info "Test 5: CAPTCHA detection"

    local probe_output
    probe_output=$(captivity probe 2>&1)

    if echo "${probe_output}" | grep -qi "captcha"; then
        log_pass "CAPTCHA correctly detected"
    else
        log_info "No CAPTCHA indicator found (portal may not use CAPTCHA)"
        log_skip "CAPTCHA not detected"
    fi
}

# --- Test 6: Login flow (with browser) --------------------------------------
test_login_flow() {
    log_info "Test 6: Login flow"

    # Check if we're already connected
    local status
    status=$(captivity probe 2>&1 | head -1)

    if echo "${status}" | grep -q "connected"; then
        log_skip "Already connected — skipping login test"
        return
    fi

    log_info "Attempting login..."
    log_info "(If CAPTCHA detected, a browser window will open)"

    captivity login --network "${NETWORK}" 2>&1 | tee "${LOG_DIR}/login.log"

    # Check if login succeeded
    sleep 3
    if ping -c 1 -W 3 google.com &>/dev/null; then
        log_pass "Login successful — internet available"
    else
        log_warn "Login may have opened browser for CAPTCHA"
        log_info "Waiting 60s for manual CAPTCHA completion..."
        local elapsed=0
        while [[ $elapsed -lt 60 ]]; do
            sleep 5
            elapsed=$((elapsed + 5))
            if ping -c 1 -W 3 google.com &>/dev/null; then
                log_pass "Login successful after ${elapsed}s (manual CAPTCHA completed)"
                return
            fi
        done
        log_fail "Login did not complete within 60s"
    fi
}

# --- Test 7: Daemon --once mode ---------------------------------------------
test_daemon_once() {
    log_info "Test 7: Daemon --once mode"

    local daemon_output
    daemon_output=$(timeout 15 captivity daemon --once --network "${NETWORK}" 2>&1 || true)
    echo "${daemon_output}" > "${LOG_DIR}/daemon_once.log"
    echo "${daemon_output}"

    if echo "${daemon_output}" | grep -qi "portal\|connected\|login"; then
        log_pass "Daemon --once completed with state transition"
    else
        log_fail "Daemon --once produced no meaningful output"
    fi
}

# --- Test 8: Verify state after login ---------------------------------------
test_post_login_state() {
    log_info "Test 8: Post-login connectivity"

    local status
    status=$(captivity probe 2>&1)
    echo "${status}" > "${LOG_DIR}/post_login.log"

    if echo "${status}" | grep -q "connected"; then
        log_pass "Post-login: connected"
    else
        log_warn "Post-login: not connected"
        log_skip "Post-login state not verified"
    fi
}

# --- Summary -----------------------------------------------------------------
summary() {
    echo ""
    echo "======================================"
    echo "  REAL PORTAL TEST SUMMARY"
    echo "======================================"
    echo -e "  ${GREEN}Passed: ${passed}${NC}"
    echo -e "  ${RED}Failed: ${failed}${NC}"
    echo -e "  ${YELLOW}Skipped: ${skipped}${NC}"
    echo "  Logs: ${LOG_DIR}"
    echo "======================================"

    if [[ ${failed} -eq 0 ]]; then
        echo -e "  ${GREEN}✓ ALL TESTS PASSED${NC}"
        exit 0
    else
        echo -e "  ${RED}✗ SOME TESTS FAILED${NC}"
        exit 1
    fi
}

# --- Main --------------------------------------------------------------------
main() {
    setup
    test_cli_available
    test_connect_network
    test_portal_active
    test_probe_detection
    test_captcha_detection
    test_login_flow
    test_daemon_once
    test_post_login_state
    summary
}

main
