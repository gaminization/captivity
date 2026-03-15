#!/bin/bash
# =============================================================================
# test_credentials.sh — Tests for captivity-creds.sh
# Part of the Captivity project
# Version: v0.2
#
# TAP-compatible test output. Uses argument validation tests that
# don't require actual secret-tool or D-Bus session.
# =============================================================================

TESTS_RUN=0
TESTS_FAILED=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CREDS_SCRIPT="${PROJECT_DIR}/scripts/captivity-creds.sh"

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
    LAST_OUTPUT=$(bash "${CREDS_SCRIPT}" "$@" 2>&1)
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

echo "# Testing captivity-creds.sh"
echo "# =========================="

# Test 1: Script exists and has valid bash syntax
if bash -n "${CREDS_SCRIPT}" 2>/dev/null; then
    pass "Script has valid bash syntax"
else
    fail "Script has valid bash syntax"
fi

# Test 2-3: No arguments exits non-zero and shows usage
run_script
assert_exit_code 1 "No arguments exits with code 1"
assert_output_contains "Usage" "No arguments shows usage text"

# Test 4-5: --help exits 0 and shows commands
run_script --help
assert_exit_code 0 "--help exits with code 0"
assert_output_contains "store" "--help mentions 'store' command"

# Test 6-7: Unknown command
run_script foobar
assert_exit_code 1 "Unknown command exits with code 1"
assert_output_contains "Unknown command" "Unknown command shows error message"

# Test 8: Store without network arg
run_script store
assert_exit_code 1 "'store' without network exits with code 1"

# Test 9: Retrieve without network arg
run_script retrieve
assert_exit_code 1 "'retrieve' without network exits with code 1"

# Test 10: Delete without network arg
run_script delete
assert_exit_code 1 "'delete' without network exits with code 1"

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
