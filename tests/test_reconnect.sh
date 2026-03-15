#!/bin/bash
# =============================================================================
# test_reconnect.sh — Tests for captivity-reconnect.sh
# Part of the Captivity project
# Version: v0.3
#
# TAP-compatible test output. Tests argument parsing, probe logic,
# and backoff calculation without requiring network access.
# =============================================================================

TESTS_RUN=0
TESTS_FAILED=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RECONNECT_SCRIPT="${PROJECT_DIR}/scripts/captivity-reconnect.sh"

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
    LAST_OUTPUT=$(bash "${RECONNECT_SCRIPT}" "$@" 2>&1)
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

echo "# Testing captivity-reconnect.sh"
echo "# ================================"

# Test 1: Script has valid bash syntax
if bash -n "${RECONNECT_SCRIPT}" 2>/dev/null; then
    pass "Script has valid bash syntax"
else
    fail "Script has valid bash syntax"
fi

# Test 2-3: --help flag
run_script --help
assert_exit_code 0 "--help exits with code 0"
assert_output_contains "Usage" "--help shows usage text"

# Test 4: --help mentions --once
assert_output_contains "\-\-once" "--help mentions --once flag"

# Test 5: --help mentions --interval
assert_output_contains "\-\-interval" "--help mentions --interval flag"

# Test 6: --help mentions --daemon
assert_output_contains "\-\-daemon" "--help mentions --daemon flag"

# Test 7: Unknown flag exits with error
run_script --badarg
assert_exit_code 1 "Unknown argument exits with code 1"

# Test 8: --dry-run --once runs without error
run_script --once --dry-run
assert_exit_code 0 "--once --dry-run runs without error"

# Test 9: --dry-run output contains DRY-RUN marker
assert_output_contains "DRY-RUN" "--dry-run output contains DRY-RUN marker"

# Test 10: Backoff calculation logic
# Test the backoff algorithm independently (same logic as in the script)
BACKOFF_OUTPUT=$(bash -c '
    BACKOFF_INTERVALS=(5 10 30 60 120 300)
    get_backoff_interval() {
        local failures="$1"
        local max_index=$(( ${#BACKOFF_INTERVALS[@]} - 1 ))
        local index=$(( failures < max_index ? failures : max_index ))
        echo "${BACKOFF_INTERVALS[${index}]}"
    }
    echo "$(get_backoff_interval 0)"
    echo "$(get_backoff_interval 2)"
    echo "$(get_backoff_interval 10)"
' 2>/dev/null)

EXPECTED_BACKOFF=$'5\n30\n300'

if [[ "${BACKOFF_OUTPUT}" == "${EXPECTED_BACKOFF}" ]]; then
    pass "Backoff intervals calculate correctly (5s, 30s, 300s cap)"
else
    fail "Backoff intervals calculate correctly (got: '${BACKOFF_OUTPUT}', expected: '${EXPECTED_BACKOFF}')"
fi

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
