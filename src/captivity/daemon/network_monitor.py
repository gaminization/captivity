"""
Event-driven network monitor.

Provides dual-layer monitoring (nmcli + DBus fallback) to capture
network state changes without polling. Pushes normalized events
to a thread-safe queue.
"""

import subprocess
import threading
import queue
import shutil
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
        """Main loop with auto-reconciliation and dual-layer fallback."""
        while self.should_run:
            if shutil.which("nmcli"):
                logger.debug("Starting nmcli monitor")
                self._run_nmcli_monitor()
            elif shutil.which("dbus-monitor"):
                logger.debug("Starting dbus-monitor fallback")
                self._run_dbus_monitor()
            else:
                logger.error("No monitoring tools available. Event loss imminent.")
                time.sleep(10)  # Crash resilience
            
            if self.should_run:
                logger.warning("Monitor subprocess exited. Restarting in 5s.")
                time.sleep(5)

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
            elif "'disconnected' state" in line or "'connecting' state" in line or "'connected (local only)' state" in line:
                return NetworkEvent.DISCONNECTED
        return None

    def _run_dbus_monitor(self) -> None:
        """Fallback: dbus-monitor parsing."""
        try:
            self._process = subprocess.Popen(
                [
                    "dbus-monitor",
                    "--system",
                    "type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged',path='/org/freedesktop/NetworkManager'"
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
                if "string \"Connectivity\"" in joined.lower():
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

    def get_event(self, timeout: float) -> Optional[NetworkEvent]:
        """Get the next network event, or None if timeout."""
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

def get_active_wifi_ssid() -> Optional[str]:
    """Get the SSID of the currently active WiFi connection."""
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
