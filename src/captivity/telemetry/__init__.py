"""
Captivity Telemetry subpackage.

Provides monitoring and statistics:
  - Session uptime tracking
  - Bandwidth usage monitoring (via /proc/net/dev)
  - Reconnect statistics and connection history

All telemetry is local-only and never transmitted externally.
"""
