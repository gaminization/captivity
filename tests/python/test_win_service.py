"""Tests for win_service module on non-Windows platforms."""

import unittest

from captivity.daemon.win_service import CaptivityService, _WIN32_AVAILABLE


class TestWinServiceStub(unittest.TestCase):
    """Test that the stub behaves correctly on non-Windows."""

    def test_win32_not_available(self):
        self.assertFalse(_WIN32_AVAILABLE)

    def test_stub_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            CaptivityService()
        self.assertIn("pywin32", str(ctx.exception))

    def test_svc_name(self):
        self.assertEqual(CaptivityService._svc_name_, "CaptivityDaemon")


class TestWinServiceMain(unittest.TestCase):
    """Test the main() entry point."""

    def test_main_exits_on_linux(self):
        from captivity.daemon.win_service import main

        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
