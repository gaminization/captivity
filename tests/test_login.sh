#!/bin/bash
# =============================================================================
# test_login.sh — Tests for captivity-login.sh
# Part of the Captivity project
# Version: v0.2
#
# TAP-compatible test output. Tests argument parsing and dry-run
# functionality without requiring network access.
# =============================================================================

TESTS_RUN=0
TESTS_FAILED=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOGIN_SCRIPT="${PROJECT_DIR}/scripts/captivity-login.sh"

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

# Run script and capture exit code + output
# Usage: run_script [args...]
# Sets: LAST_EXIT, LAST_OUTPUT
run_script() {
    LAST_OUTPUT=$(bash "${LOGIN_SCRIPT}" "$@" 2>&1)
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

# --- Tests -------------------------------------------------------------------

echo "# Testing captivity-login.sh"
echo "# ==========================="

# Test 1: Script exists and has valid bash syntax
if bash -n "${LOGIN_SCRIPT}" 2>/dev/null; then
    pass "Script has valid bash syntax"
else
    fail "Script has valid bash syntax"
fi

# Test 2-3: No arguments exits non-zero and shows usage
run_script
assert_exit_code 1 "No arguments exits with code 1"
assert_output_contains "Usage" "No arguments shows usage text"

# Test 4-7: --help flag
run_script --help
assert_exit_code 0 "--help exits with code 0"
assert_output_contains "\-\-network" "--help mentions --network flag"
assert_output_contains "\-\-portal" "--help mentions --portal flag"
assert_output_contains "\-\-dry-run" "--help mentions --dry-run flag"

# Test 8: Unknown flag exits with error
run_script --unknown
assert_exit_code 1 "Unknown flag exits with code 1"

# Test 9-10: Missing --network value
run_script --portal http://example.com
assert_exit_code 1 "Missing --network exits with code 1"
assert_output_contains "Missing required" "Missing --network shows helpful error message"

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
