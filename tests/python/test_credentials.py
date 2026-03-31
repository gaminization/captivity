"""Tests for captivity.core.credentials module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.credentials import (
    store,
    retrieve,
    delete,
    list_networks,
    CredentialError,
)


class TestCredentials(unittest.TestCase):
    """Test credential management."""

    @patch("captivity.core.credentials.shutil.which", return_value="/usr/bin/secret-tool")
    @patch("captivity.core.credentials.subprocess.run")
    def test_store_calls_secret_tool(self, mock_run, mock_which):
        """Store invokes secret-tool for username and password."""
        mock_run.return_value = MagicMock(returncode=0)

        store("test_network", "user", "pass")

        self.assertEqual(mock_run.call_count, 2)
        # First call stores username
        args_0 = mock_run.call_args_list[0]
        self.assertIn("store", args_0[0][0])
        self.assertEqual(args_0[1]["input"], b"user")
        # Second call stores password
        args_1 = mock_run.call_args_list[1]
        self.assertIn("store", args_1[0][0])
        self.assertEqual(args_1[1]["input"], b"pass")

    @patch("captivity.core.credentials.shutil.which", return_value="/usr/bin/secret-tool")
    @patch("captivity.core.credentials.subprocess.run")
    def test_retrieve_returns_credentials(self, mock_run, mock_which):
        """Retrieve returns username and password tuple."""
        def side_effect(cmd, **kwargs):
            result = MagicMock()
            if "username" in cmd:
                result.stdout = b"testuser"
            else:
                result.stdout = b"testpass"
            result.returncode = 0
            return result

        mock_run.side_effect = side_effect
        username, password = retrieve("test_net")
        self.assertEqual(username, "testuser")
        self.assertEqual(password, "testpass")

    @patch("captivity.core.credentials.shutil.which", return_value="/usr/bin/secret-tool")
    @patch("captivity.core.credentials.subprocess.run")
    def test_retrieve_raises_on_empty(self, mock_run, mock_which):
        """Retrieve raises CredentialError for empty results."""
        result = MagicMock()
        result.stdout = b""
        result.returncode = 0
        mock_run.return_value = result

        with self.assertRaises(CredentialError):
            retrieve("missing_net")

    @patch("captivity.core.credentials.shutil.which", return_value="/usr/bin/secret-tool")
    @patch("captivity.core.credentials.subprocess.run")
    def test_delete_calls_clear(self, mock_run, mock_which):
        """Delete invokes secret-tool clear for both fields."""
        mock_run.return_value = MagicMock(returncode=0)

        delete("test_net")

        self.assertEqual(mock_run.call_count, 2)
        for call_args in mock_run.call_args_list:
            self.assertIn("clear", call_args[0][0])

    @patch("captivity.core.credentials.shutil.which", return_value=None)
    def test_store_raises_without_secret_tool(self, mock_which):
        """Store raises CredentialError if secret-tool missing."""
        with self.assertRaises(CredentialError) as ctx:
            store("net", "user", "pass")
        self.assertIn("secret-tool not found", str(ctx.exception))

    @patch("captivity.core.credentials.shutil.which", return_value="/usr/bin/secret-tool")
    @patch("captivity.core.credentials.subprocess.run")
    def test_list_networks_parses_output(self, mock_run, mock_which):
        """List parses secret-tool search output for network names."""
        result = MagicMock()
        # secret-tool writes metadata to stdout, attributes to stderr
        result.stdout = (
            "[/org/freedesktop/secrets/1]\n"
            "label = captivity-campus_wifi-username\n"
            "\n"
            "[/org/freedesktop/secrets/2]\n"
            "label = captivity-coffee_shop-password\n"
        )
        result.stderr = (
            "attribute.application = captivity\n"
            "attribute.network = campus_wifi\n"
            "attribute.field = username\n"
            "attribute.application = captivity\n"
            "attribute.network = coffee_shop\n"
            "attribute.field = password\n"
        )
        result.returncode = 0
        mock_run.return_value = result

        networks = list_networks()
        self.assertEqual(networks, ["campus_wifi", "coffee_shop"])

    @patch("captivity.core.credentials.shutil.which", return_value="/usr/bin/secret-tool")
    @patch("captivity.core.credentials.subprocess.run")
    def test_list_returns_empty_for_no_entries(self, mock_run, mock_which):
        """List returns empty list when no credentials stored."""
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        mock_run.return_value = result

        networks = list_networks()
        self.assertEqual(networks, [])


if __name__ == "__main__":
    unittest.main()
