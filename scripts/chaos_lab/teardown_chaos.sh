#!/usr/bin/env bash
# Captivity Chaos Lab - Teardown Script

set -euo pipefail

IFACE=${1:-wlan0}

echo "Tearing down Chaos Lab on interface $IFACE"

# Remove tc rules
tc qdisc del dev "$IFACE" root 2>/dev/null || echo "No tc rules to remove"

# Remove iptables redirect
# We use a pattern match to flush our specific rules
iptables -t nat -F OUTPUT 2>/dev/null || echo "No iptables rules to remove"

echo "Chaos Lab completely deactivated."
