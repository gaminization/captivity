"""
Windows Service wrapper for the Captivity daemon.

Allows Captivity to be managed via the Windows Service Control Manager
(services.msc, sc.exe, Get-Service, etc.).

Requires: pywin32 (automatically installed on Windows via pyproject.toml).

Install:
    python -m captivity.daemon.win_service install
Start:
    python -m captivity.daemon.win_service start
Stop:
    python -m captivity.daemon.win_service stop
Remove:
    python -m captivity.daemon.win_service remove
"""

import sys
import threading

from captivity.utils.logging import get_logger

logger = get_logger("win_service")

# Guard the win32 imports so the module can be safely imported on
# non-Windows platforms (e.g. during test collection or type checking).
try:
    import win32serviceutil  # type: ignore[import-untyped]
    import win32service  # type: ignore[import-untyped]
    import win32event  # type: ignore[import-untyped]

    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False


if _WIN32_AVAILABLE:

    class CaptivityService(win32serviceutil.ServiceFramework):
        """Windows Service Framework implementation for the Captivity daemon."""

        _svc_name_ = "CaptivityDaemon"
        _svc_display_name_ = "Captivity — Autonomous Captive Portal Client"
        _svc_description_ = (
            "Automatically detects and logs into captive WiFi portals "
            "without any user intervention."
        )

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._runner = None
            self._thread = None

        def SvcStop(self):
            """Called by the SCM to stop the service."""
            logger.info(
                "Windows SCM stop request received",
                extra={"action": "STOP"},
            )
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

            if self._runner:
                self._runner.should_run = False
                if self._runner.monitor:
                    self._runner.monitor.stop()

            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            """Called by the SCM to start the service."""
            logger.info(
                "Windows SCM start request received",
                extra={"action": "START"},
            )
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)

            # Import here to avoid circular imports at module level
            from captivity.daemon.runner import DaemonRunner

            self._runner = DaemonRunner()
            self._thread = threading.Thread(
                target=self._runner.run,
                name="CaptivityDaemonThread",
                daemon=True,
            )
            self._thread.start()

            # Block until stop event is signaled
            win32event.WaitForSingleObject(
                self.stop_event, win32event.INFINITE
            )

            # Wait for daemon thread to finish cleanly
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=10.0)

            logger.info(
                "Windows service stopped cleanly",
                extra={"action": "STOPPED"},
            )

else:
    # Provide a stub so the module doesn't crash on import during tests
    class CaptivityService:  # type: ignore[no-redef]
        """Stub for non-Windows platforms."""

        _svc_name_ = "CaptivityDaemon"

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "CaptivityService requires pywin32 and Windows. "
                "This platform is not supported."
            )


def main():
    """Entry point for service management CLI."""
    if not _WIN32_AVAILABLE:
        print("ERROR: pywin32 is not installed. This command requires Windows.")
        sys.exit(1)
    win32serviceutil.HandleCommandLine(CaptivityService)


if __name__ == "__main__":
    main()
