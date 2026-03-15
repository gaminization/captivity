"""Tests for captivity.core.parser module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.parser import (
    FormField,
    LoginForm,
    PortalHTMLParser,
    find_login_form,
    parse_portal_page,
)


class TestFormField(unittest.TestCase):
    """Test FormField properties."""

    def test_password_field_by_type(self):
        f = FormField("pw", field_type="password")
        self.assertTrue(f.is_password)
        self.assertFalse(f.is_username)

    def test_password_field_by_name(self):
        f = FormField("userPassword", field_type="text")
        self.assertTrue(f.is_password)

    def test_username_field_by_name(self):
        f = FormField("userId", field_type="text")
        self.assertTrue(f.is_username)

    def test_email_field_is_username(self):
        f = FormField("email", field_type="email")
        self.assertTrue(f.is_username)

    def test_hidden_field(self):
        f = FormField("token", value="abc", field_type="hidden")
        self.assertTrue(f.is_hidden)
        self.assertFalse(f.is_username)
        self.assertFalse(f.is_password)

    def test_password_type_not_username(self):
        """Password-type fields should NOT be detected as username."""
        f = FormField("loginPassword", field_type="password")
        self.assertFalse(f.is_username)


class TestLoginForm(unittest.TestCase):
    """Test LoginForm."""

    def _make_form(self):
        form = LoginForm(action="/login", method="POST")
        form.fields = [
            FormField("token", "abc123", "hidden"),
            FormField("userId", "", "text"),
            FormField("password", "", "password"),
            FormField("submit", "Login", "submit"),
        ]
        return form

    def test_finds_username_field(self):
        form = self._make_form()
        self.assertEqual(form.username_field.name, "userId")

    def test_finds_password_field(self):
        form = self._make_form()
        self.assertEqual(form.password_field.name, "password")

    def test_build_payload(self):
        form = self._make_form()
        payload = form.build_payload("user1", "pass1")
        self.assertEqual(payload["userId"], "user1")
        self.assertEqual(payload["password"], "pass1")
        self.assertEqual(payload["token"], "abc123")
        self.assertEqual(payload["submit"], "Login")


class TestPortalHTMLParser(unittest.TestCase):
    """Test HTML parsing."""

    def test_parses_simple_form(self):
        html = """
        <html><body>
        <form action="/login" method="POST">
            <input type="hidden" name="token" value="xyz">
            <input type="text" name="username">
            <input type="password" name="pass">
            <input type="submit" name="submit" value="Sign In">
        </form>
        </body></html>
        """
        parser = PortalHTMLParser()
        parser.feed(html)
        self.assertEqual(len(parser.forms), 1)
        form = parser.forms[0]
        self.assertEqual(form.action, "/login")
        self.assertEqual(form.method, "POST")
        self.assertEqual(len(form.fields), 4)

    def test_parses_multiple_forms(self):
        html = """
        <form action="/search"><input name="q" type="text"></form>
        <form action="/login">
            <input name="user" type="text">
            <input name="pass" type="password">
        </form>
        """
        parser = PortalHTMLParser()
        parser.feed(html)
        self.assertEqual(len(parser.forms), 2)

    def test_ignores_inputs_outside_form(self):
        html = '<input name="orphan" type="text">'
        parser = PortalHTMLParser()
        parser.feed(html)
        self.assertEqual(len(parser.forms), 0)

    def test_skips_inputs_without_name(self):
        html = '<form><input type="text"><input name="user" type="text"></form>'
        parser = PortalHTMLParser()
        parser.feed(html)
        self.assertEqual(len(parser.forms[0].fields), 1)


class TestFindLoginForm(unittest.TestCase):
    """Test login form selection."""

    def test_prefers_form_with_both_fields(self):
        form1 = LoginForm(action="/search")
        form1.fields = [FormField("q", field_type="text")]

        form2 = LoginForm(action="/login")
        form2.fields = [
            FormField("username", field_type="text"),
            FormField("password", field_type="password"),
        ]

        result = find_login_form([form1, form2])
        self.assertEqual(result.action, "/login")

    def test_returns_none_for_empty(self):
        self.assertIsNone(find_login_form([]))


class TestParsePortalPage(unittest.TestCase):
    """Test end-to-end portal page parsing."""

    @patch("captivity.core.parser.requests.get")
    def test_parses_portal_page(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = """
        <form action="/auth/login" method="POST">
            <input type="hidden" name="csrf" value="tok123">
            <input type="text" name="userId">
            <input type="password" name="password">
        </form>
        """
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        form = parse_portal_page("http://portal.test/")
        self.assertIsNotNone(form)
        self.assertEqual(form.action, "http://portal.test/auth/login")
        self.assertEqual(len(form.fields), 3)

    @patch("captivity.core.parser.requests.get")
    def test_returns_none_on_no_forms(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body>No forms here</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        form = parse_portal_page("http://portal.test/")
        self.assertIsNone(form)


if __name__ == "__main__":
    unittest.main()
