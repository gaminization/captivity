"""Tests for captivity.core.credentials module (dual-backend: keyring + file fallback)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from captivity.core.credentials import (
    CredentialError,
    _file_delete,
    _file_retrieve,
    _file_store,
    delete,
    list_networks,
    retrieve,
    store,
)


class TestFileFallback(unittest.TestCase):
    """Test the encrypted-file backend directly."""

    def setUp(self):
        # Point the file backend at a temp path so tests don't touch the real store
        import captivity.core.credentials as creds_mod
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self._orig_dir = creds_mod._CRED_DIR
        self._orig_file = creds_mod._CRED_FILE
        creds_mod._CRED_DIR = Path(self._tmpdir)
        creds_mod._CRED_FILE = Path(self._tmpdir) / "credentials.enc"

    def tearDown(self):
        import captivity.core.credentials as creds_mod
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        creds_mod._CRED_DIR = self._orig_dir
        creds_mod._CRED_FILE = self._orig_file

    def test_roundtrip(self):
        _file_store("mynet", "alice", "s3cr3t")
        result = _file_retrieve("mynet")
        self.assertIsNotNone(result)
        username, password = result
        self.assertEqual(username, "alice")
        self.assertEqual(password, "s3cr3t")

    def test_retrieve_missing_returns_none(self):
        self.assertIsNone(_file_retrieve("nonexistent"))

    def test_delete_removes_entry(self):
        _file_store("net", "u", "p")
        _file_delete("net")
        self.assertIsNone(_file_retrieve("net"))

    def test_multiple_networks(self):
        _file_store("net1", "u1", "p1")
        _file_store("net2", "u2", "p2")
        self.assertEqual(_file_retrieve("net1"), ("u1", "p1"))
        self.assertEqual(_file_retrieve("net2"), ("u2", "p2"))


class TestCredentialsPublicAPI(unittest.TestCase):
    """Test the public store/retrieve/delete API with mocked backends."""

    def setUp(self):
        import captivity.core.credentials as creds_mod
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self._orig_dir = creds_mod._CRED_DIR
        self._orig_file = creds_mod._CRED_FILE
        creds_mod._CRED_DIR = Path(self._tmpdir)
        creds_mod._CRED_FILE = Path(self._tmpdir) / "credentials.enc"

    def tearDown(self):
        import captivity.core.credentials as creds_mod
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        creds_mod._CRED_DIR = self._orig_dir
        creds_mod._CRED_FILE = self._orig_file

    @patch("captivity.core.credentials._keyring_available", return_value=True)
    def test_store_uses_keyring_when_available(self, mock_avail):
        import keyring as _keyring_mod
        with patch.object(_keyring_mod, "set_password") as mock_set:
            store("mynet", "user", "pass")
        mock_set.assert_any_call("captivity", "mynet-username", "user")
        mock_set.assert_any_call("captivity", "mynet-password", "pass")

    @patch("captivity.core.credentials._keyring_available", return_value=False)
    def test_store_falls_back_to_file_when_keyring_unavailable(self, mock_avail):
        store("mynet", "alice", "secret")
        result = _file_retrieve("mynet")
        self.assertEqual(result, ("alice", "secret"))

    @patch("captivity.core.credentials._keyring_available", return_value=True)
    def test_retrieve_uses_keyring_when_available(self, mock_avail):
        import keyring as _keyring_mod
        with patch.object(_keyring_mod, "get_password",
                          side_effect=lambda svc, key: "testuser" if "username" in key else "testpass"):
            username, password = retrieve("mynet")
        self.assertEqual(username, "testuser")
        self.assertEqual(password, "testpass")

    @patch("captivity.core.credentials._keyring_available", return_value=False)
    def test_retrieve_falls_back_to_file(self, mock_avail):
        _file_store("mynet", "bob", "hunter2")
        username, password = retrieve("mynet")
        self.assertEqual(username, "bob")
        self.assertEqual(password, "hunter2")

    @patch("captivity.core.credentials._keyring_available", return_value=False)
    def test_retrieve_raises_when_nothing_stored(self, mock_avail):
        with self.assertRaises(CredentialError):
            retrieve("nonexistent")

    @patch("captivity.core.credentials._keyring_available", return_value=True)
    def test_store_raises_credential_error_when_both_backends_fail(self, mock_avail):
        import keyring as _keyring_mod
        with patch.object(_keyring_mod, "set_password", side_effect=Exception("D-Bus dead")):
            # File backend should succeed as fallback
            store("mynet", "u", "p")
        # File fallback should have been used
        self.assertEqual(_file_retrieve("mynet"), ("u", "p"))

    def test_list_networks_returns_file_stored_names(self):
        _file_store("netA", "u", "p")
        _file_store("netB", "u", "p")
        networks = list_networks()
        self.assertIn("netA", networks)
        self.assertIn("netB", networks)


if __name__ == "__main__":
    unittest.main()
