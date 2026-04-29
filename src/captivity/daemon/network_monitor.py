"""
Cross-platform event-driven network monitor.

Provides platform-aware monitoring:
  - Linux: nmcli monitor (primary) + dbus-monitor (fallback)
  - macOS/Windows: polling-based fallback using HTTP probes

Pushes normalized NetworkEvent instances to a thread-safe queue.
"""

import queue
import shutil
import subprocess
import sys
import threading
import time
from enum import Enum, auto
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("network_monitor")


class NetworkEvent(Enum):
    """Normalized network events."""

    CONNECTED = auto()
    DISCONNECTED = auto()
    PORTAL = auto()


class NetworkMonitor(threading.Thread):
    """Background thread that monitors for network changes.

    Yields normalized NetworkEvent instances to its queue.
    """

    def __init__(self) -> None:
        super().__init__(name="NetworkMonitor", daemon=True)
        self.event_queue: queue.Queue[NetworkEvent] = queue.Queue()
        self.should_run = True
        self._process: Optional[subprocess.Popen] = None

    def stop(self) -> None:
        """Stop the monitor thread."""
        self.should_run = False
        if self._process:
            self._process.terminate()

    def run(self) -> None:
        """Main loop with platform-aware monitoring strategy."""
        while self.should_run:
            if sys.platform == "linux":
                self._run_linux_monitor()
            else:
                # macOS and Windows: polling fallback
                logger.info(
                    "Using polling monitor for platform",
                    extra={"platform": sys.platform},
                )
                self._run_polling_monitor()

            if self.should_run:
                logger.warning("Monitor subprocess exited. Restarting in 5s.")
                time.sleep(5)

    def _run_linux_monitor(self) -> None:
        """Linux-specific: nmcli primary, dbus-monitor fallback."""
        if shutil.which("nmcli"):
            logger.debug("Starting nmcli monitor")
            self._run_nmcli_monitor()
        elif shutil.which("dbus-monitor"):
            logger.debug("Starting dbus-monitor fallback")
            self._run_dbus_monitor()
        else:
            logger.error("No Linux monitoring tools available.")
            self._run_polling_monitor()

    def _run_nmcli_monitor(self) -> None:
        """Run nmcli monitor and parse output."""
        try:
            self._process = subprocess.Popen(
                ["nmcli", "monitor"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,  # Line buffered
            )

            if not self._process.stdout:
                return

            for line in iter(self._process.stdout.readline, ""):
                if not self.should_run:
                    break
                event = self._normalize_nmcli_line(line.strip())
                if event:
                    logger.debug("Normalized event: %s", event.name)
                    self.event_queue.put(event)

        except Exception as exc:
            logger.error("nmcli monitor crashed: %s", exc)
        finally:
            if self._process:
                self._process.terminate()

    def _normalize_nmcli_line(self, line: str) -> Optional[NetworkEvent]:
        """Normalize raw nmcli output."""
        line = line.lower()
        if "networkmanager is now in the" in line:
            if "'connected' state" in line or "'connected (global)' state" in line:
                return NetworkEvent.CONNECTED
            elif "'connected (site only)' state" in line:
                return NetworkEvent.PORTAL
            elif (
                "'disconnected' state" in line
                or "'connecting' state" in line
                or "'connected (local only)' state" in line
            ):
                return NetworkEvent.DISCONNECTED
        return None

    def _run_dbus_monitor(self) -> None:
        """Fallback: dbus-monitor parsing."""
        try:
            self._process = subprocess.Popen(
                [
                    "dbus-monitor",
                    "--system",
                    "type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged',path='/org/freedesktop/NetworkManager'",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )

            if not self._process.stdout:
                return

            # Basic parsing: look for 'uint32 4' (FULL), 'uint32 2' (PORTAL), etc.
            # This is fragile but acts as a fallback.
            buffer = []
            for line in iter(self._process.stdout.readline, ""):
                if not self.should_run:
                    break

                buffer.append(line.strip())
                if len(buffer) > 10:
                    buffer.pop(0)

                joined = " ".join(buffer)
                if 'string "Connectivity"' in joined.lower():
                    if "uint32 4" in joined.lower():
                        self.event_queue.put(NetworkEvent.CONNECTED)
                        buffer.clear()
                    elif "uint32 2" in joined.lower():
                        self.event_queue.put(NetworkEvent.PORTAL)
                        buffer.clear()
                    elif "uint32 1" in joined.lower():
                        self.event_queue.put(NetworkEvent.DISCONNECTED)
                        buffer.clear()

        except Exception as exc:
            logger.error("dbus-monitor crashed: %s", exc)
        finally:
            if self._process:
                self._process.terminate()

    def _run_polling_monitor(self, interval: float = 10.0) -> None:
        """Cross-platform fallback: poll connectivity via HTTP probe.

        Used on macOS, Windows, or Linux when nmcli/dbus are unavailable.
        Emits CONNECTED or DISCONNECTED based on HTTP 204 probe results.
        """
        import requests

        probe_url = "http://clients3.google.com/generate_204"
        last_state: Optional[NetworkEvent] = None

        while self.should_run:
            try:
                resp = requests.get(probe_url, timeout=5, allow_redirects=False)
                if resp.status_code == 204:
                    current = NetworkEvent.CONNECTED
                elif resp.status_code in (301, 302, 307, 308):
                    current = NetworkEvent.PORTAL
                else:
                    current = NetworkEvent.DISCONNECTED
            except Exception:
                current = NetworkEvent.DISCONNECTED

            if current != last_state:
                logger.debug(
                    "Polling monitor state change",
                    extra={
                        "old": last_state.name if last_state else "NONE",
                        "new": current.name,
                    },
                )
                self.event_queue.put(current)
                last_state = current

            time.sleep(interval)

    def get_event(self, timeout: float) -> Optional[NetworkEvent]:
        """Get the next network event, or None if timeout."""
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return None


def get_active_wifi_ssid() -> Optional[str]:
    """Get the SSID of the currently active WiFi connection.

    Platform support:
      - Linux: nmcli
      - macOS: airport utility
      - Windows: netsh wlan
    """
    if sys.platform == "linux":
        return _get_ssid_linux()
    elif sys.platform == "darwin":
        return _get_ssid_macos()
    elif sys.platform == "win32":
        return _get_ssid_windows()
    else:
        logger.warning("Unsupported platform for SSID detection: %s", sys.platform)
        return None


def _get_ssid_linux() -> Optional[str]:
    """Get active WiFi SSID on Linux via nmcli."""
    if not shutil.which("nmcli"):
        return None
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if line.startswith("yes:"):
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    return ssid
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _get_ssid_macos() -> Optional[str]:
    """Get active WiFi SSID on macOS via airport utility."""
    airport_path = (
        "/System/Library/PrivateFrameworks/Apple80211.framework"
        "/Versions/Current/Resources/airport"
    )
    try:
        result = subprocess.run(
            [airport_path, "-I"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("SSID:"):
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    return ssid
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass
    return None


def _get_ssid_windows() -> Optional[str]:
    """Get active WiFi SSID on Windows via netsh."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            # Match "SSID" but not "BSSID"
            if line.startswith("SSID") and not line.startswith("BSSID"):
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    return ssid
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass
    return None
