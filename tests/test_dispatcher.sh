#!/bin/bash
# =============================================================================
# test_dispatcher.sh — Tests for captivity-dispatcher.sh
# Part of the Captivity project
# Version: v0.4
#
# TAP-compatible test output. Tests argument parsing and event filtering
# without requiring NetworkManager or root access.
# =============================================================================

TESTS_RUN=0
TESTS_FAILED=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DISPATCHER_SCRIPT="${PROJECT_DIR}/scripts/captivity-dispatcher.sh"

# --- TAP Helpers -------------------------------------------------------------
pass() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo "ok ${TESTS_RUN} - $1"
}

fail() {
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo "not ok ${TESTS_RUN} - $1"
}

run_script() {
    # Override CAPTIVITY_DIR to point to project dir to avoid needing /opt
    LAST_OUTPUT=$(CAPTIVITY_DIR="${PROJECT_DIR}" bash "${DISPATCHER_SCRIPT}" "$@" 2>&1)
    LAST_EXIT=$?
}

assert_exit_code() {
    local expected="$1"
    local desc="$2"
    if [[ "${LAST_EXIT}" -eq "${expected}" ]]; then
        pass "${desc}"
    else
        fail "${desc} (expected exit ${expected}, got ${LAST_EXIT})"
    fi
}

assert_output_contains() {
    local needle="$1"
    local desc="$2"
    if echo "${LAST_OUTPUT}" | grep -q "${needle}"; then
        pass "${desc}"
    else
        fail "${desc} (output did not contain '${needle}')"
    fi
}

assert_output_not_contains() {
    local needle="$1"
    local desc="$2"
    if echo "${LAST_OUTPUT}" | grep -q "${needle}"; then
        fail "${desc} (output unexpectedly contained '${needle}')"
    else
        pass "${desc}"
    fi
}

# --- Tests -------------------------------------------------------------------

echo "# Testing captivity-dispatcher.sh"
echo "# ================================="

# Test 1: Script has valid bash syntax
if bash -n "${DISPATCHER_SCRIPT}" 2>/dev/null; then
    pass "Script has valid bash syntax"
else
    fail "Script has valid bash syntax"
fi

# Test 2: No arguments shows usage
run_script
assert_exit_code 1 "No arguments exits with code 1"

# Test 3: No arguments mentions usage
assert_output_contains "Usage" "No arguments shows usage text"

# Test 4: Non-WiFi interface should be silently ignored (exit 0)
# Use eth0 which is not a WiFi interface pattern
run_script eth0 up
assert_exit_code 0 "Non-WiFi interface (eth0) exits cleanly"

# Test 5: WiFi interface name detection via pattern
# Test the is_wifi_interface function indirectly — wlan0 should trigger login path
# Since we don't have NM or the reconnect script in /opt, it will try and log an error
# but the exit code should still be 0 (dispatcher scripts should not fail)
run_script wlan0 down
assert_exit_code 0 "WiFi interface (wlan0 down) is recognized and handled"

# Test 6: wlp-style interface is also recognized
run_script wlp2s0 down
assert_exit_code 0 "WiFi interface (wlp2s0 down) is recognized and handled"

# Test 7: Install dispatcher has valid syntax
INSTALL_SCRIPT="${PROJECT_DIR}/scripts/install-dispatcher.sh"
if bash -n "${INSTALL_SCRIPT}" 2>/dev/null; then
    pass "install-dispatcher.sh has valid bash syntax"
else
    fail "install-dispatcher.sh has valid bash syntax"
fi

# Test 8: Install script requires root
LAST_OUTPUT=$(bash "${INSTALL_SCRIPT}" 2>&1)
LAST_EXIT=$?
assert_exit_code 1 "install-dispatcher.sh requires root (exits 1 without sudo)"

# Test 9: Install script error message mentions root/sudo
assert_output_contains "root" "install-dispatcher.sh mentions root requirement"

# Test 10: Install help flag
LAST_OUTPUT=$(bash "${INSTALL_SCRIPT}" --help 2>&1)
LAST_EXIT=$?
assert_exit_code 0 "install-dispatcher.sh --help exits 0"

# --- Summary -----------------------------------------------------------------
echo
echo "1..${TESTS_RUN}"
if [[ ${TESTS_FAILED} -gt 0 ]]; then
    echo "# FAILED: ${TESTS_FAILED}/${TESTS_RUN} tests failed"
    exit 1
else
    echo "# PASSED: All ${TESTS_RUN} tests passed"
    exit 0
fi
