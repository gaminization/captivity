"""Tests for captivity.testing.scenarios module."""

import unittest

from captivity.testing.scenarios import SCENARIOS, Scenario


class TestScenario(unittest.TestCase):
    """Test Scenario dataclass."""

    def test_defaults(self):
        s = Scenario(name="test")
        self.assertEqual(s.name, "test")
        self.assertEqual(s.portal_title, "WiFi Login")
        self.assertIn("username", s.form_fields)
        self.assertEqual(s.session_duration, 0)
        self.assertFalse(s.require_terms)

    def test_custom_fields(self):
        s = Scenario(
            name="custom",
            username_field="email",
            password_field="pass",
            form_fields={"email": "", "pass": ""},
        )
        self.assertEqual(s.username_field, "email")
        self.assertEqual(s.password_field, "pass")


class TestBuiltinScenarios(unittest.TestCase):
    """Test built-in scenario definitions."""

    def test_scenarios_exist(self):
        self.assertGreaterEqual(len(SCENARIOS), 9)

    def test_simple_scenario(self):
        s = SCENARIOS["simple"]
        self.assertEqual(s.name, "simple")
        self.assertFalse(s.require_terms)

    def test_terms_scenario(self):
        s = SCENARIOS["terms"]
        self.assertTrue(s.require_terms)
        self.assertIn("accept_terms", s.form_fields)

    def test_session_expiry_scenario(self):
        s = SCENARIOS["session_expiry"]
        self.assertGreater(s.session_duration, 0)

    def test_rate_limited_scenario(self):
        s = SCENARIOS["rate_limited"]
        self.assertGreater(s.rate_limit, 0)

    def test_flaky_scenario(self):
        s = SCENARIOS["flaky"]
        self.assertGreater(s.fail_first_n, 0)

    def test_slow_scenario(self):
        s = SCENARIOS["slow"]
        self.assertGreater(s.latency_ms, 0)

    def test_custom_fields_scenario(self):
        s = SCENARIOS["custom_fields"]
        self.assertNotEqual(s.username_field, "username")

    def test_email_only_scenario(self):
        s = SCENARIOS["email_only"]
        self.assertEqual(s.password_field, "")

    def test_all_have_names(self):
        for key, s in SCENARIOS.items():
            self.assertEqual(key, s.name)

    def test_all_have_descriptions(self):
        for s in SCENARIOS.values():
            self.assertTrue(len(s.description) > 0)


if __name__ == "__main__":
    unittest.main()
