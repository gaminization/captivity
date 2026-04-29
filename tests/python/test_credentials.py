"""Tests for captivity.core.credentials module."""

import unittest
from unittest.mock import patch

from captivity.core.credentials import (
    store,
    retrieve,
    delete,
    list_networks,
    CredentialError,
)


class TestCredentials(unittest.TestCase):
    """Test credential management."""

    @patch("captivity.core.credentials.keyring.set_password")
    def test_store_calls_keyring(self, mock_set_password):
        """Store invokes keyring for username and password."""
        store("test_network", "user", "pass")

        self.assertEqual(mock_set_password.call_count, 2)
        mock_set_password.assert_any_call("captivity", "test_network-username", "user")
        mock_set_password.assert_any_call("captivity", "test_network-password", "pass")

    @patch("captivity.core.credentials.keyring.get_password")
    def test_retrieve_returns_credentials(self, mock_get_password):
        """Retrieve returns username and password tuple."""

        def side_effect(service, key):
            if "username" in key:
                return "testuser"
            return "testpass"

        mock_get_password.side_effect = side_effect
        username, password = retrieve("test_net")
        self.assertEqual(username, "testuser")
        self.assertEqual(password, "testpass")

    @patch("captivity.core.credentials.keyring.get_password", return_value=None)
    def test_retrieve_raises_on_empty(self, mock_get_password):
        """Retrieve raises CredentialError for empty results."""
        with self.assertRaises(CredentialError):
            retrieve("missing_net")

    @patch("captivity.core.credentials.keyring.delete_password")
    def test_delete_calls_clear(self, mock_delete_password):
        """Delete invokes keyring delete for both fields."""
        delete("test_net")

        self.assertEqual(mock_delete_password.call_count, 2)
        mock_delete_password.assert_any_call("captivity", "test_net-username")
        mock_delete_password.assert_any_call("captivity", "test_net-password")

    @patch("captivity.core.credentials.keyring.set_password")
    def test_store_raises_on_error(self, mock_set_password):
        """Store raises CredentialError if keyring fails."""
        mock_set_password.side_effect = Exception("Keyring locked")
        with self.assertRaises(CredentialError) as ctx:
            store("net", "user", "pass")
        self.assertIn("Failed to store credentials", str(ctx.exception))

    def test_list_returns_empty(self):
        """List returns empty list since keyring API is limited."""
        networks = list_networks()
        self.assertEqual(networks, [])


if __name__ == "__main__":
    unittest.main()
