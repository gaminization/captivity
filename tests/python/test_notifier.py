"""Tests for captivity.ui.notifier module."""

import unittest
from unittest.mock import patch

from captivity.ui.notifier import (
    Notifier,
    _has_notify_send,
    _send_via_notify_send,
)


class TestHasNotifySend(unittest.TestCase):
    """Test notify-send availability check."""

    @patch("captivity.ui.notifier.shutil.which")
    def test_available(self, mock_which):
        mock_which.return_value = "/usr/bin/notify-send"
        self.assertTrue(_has_notify_send())

    @patch("captivity.ui.notifier.shutil.which")
    def test_not_available(self, mock_which):
        mock_which.return_value = None
        self.assertFalse(_has_notify_send())


class TestSendViaNotifySend(unittest.TestCase):
    """Test notify-send subprocess call."""

    @patch("captivity.ui.notifier.subprocess.run")
    def test_sends_notification(self, mock_run):
        result = _send_via_notify_send("Title", "Body")
        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("notify-send", args)
        self.assertIn("Title", args)
        self.assertIn("Body", args)

    @patch("captivity.ui.notifier.subprocess.run")
    def test_handles_timeout(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("notify-send", 5)
        result = _send_via_notify_send("Title", "Body")
        self.assertFalse(result)


class TestNotifier(unittest.TestCase):
    """Test Notifier class."""

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    def test_enabled_when_available(self, mock_has):
        n = Notifier()
        self.assertTrue(n.available)
        self.assertTrue(n.enabled)

    @patch("captivity.ui.notifier._has_notify_send", return_value=False)
    def test_disabled_when_unavailable(self, mock_has):
        n = Notifier()
        self.assertFalse(n.available)

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    @patch("captivity.ui.notifier._send_via_notify_send", return_value=True)
    def test_send(self, mock_send, mock_has):
        n = Notifier()
        result = n.send("Test", "Body")
        self.assertTrue(result)

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    def test_disabled_skips(self, mock_has):
        n = Notifier(enabled=False)
        result = n.send("Test", "Body")
        self.assertFalse(result)

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    @patch("captivity.ui.notifier._send_via_notify_send", return_value=True)
    def test_notify_login_success(self, mock_send, mock_has):
        n = Notifier()
        result = n.notify_login_success("TestNet")
        self.assertTrue(result)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertIn("TestNet", call_kwargs[1]["body"])

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    @patch("captivity.ui.notifier._send_via_notify_send", return_value=True)
    def test_notify_login_failure(self, mock_send, mock_has):
        n = Notifier()
        result = n.notify_login_failure("TestNet", "timeout")
        self.assertTrue(result)

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    @patch("captivity.ui.notifier._send_via_notify_send", return_value=True)
    def test_notify_portal_detected(self, mock_send, mock_has):
        n = Notifier()
        result = n.notify_portal_detected("TestNet")
        self.assertTrue(result)

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    @patch("captivity.ui.notifier._send_via_notify_send", return_value=True)
    def test_notify_session_expired(self, mock_send, mock_has):
        n = Notifier()
        result = n.notify_session_expired("TestNet")
        self.assertTrue(result)

    @patch("captivity.ui.notifier._has_notify_send", return_value=True)
    @patch("captivity.ui.notifier._send_via_notify_send", return_value=True)
    def test_notify_daemon_started(self, mock_send, mock_has):
        n = Notifier()
        result = n.notify_daemon_started()
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
