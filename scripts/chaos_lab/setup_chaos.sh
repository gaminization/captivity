#!/usr/bin/env bash
# Captivity Chaos Lab - Setup Script
# Injects chaos into the wlan0 interface using tc (Traffic Control) and iptables

set -euo pipefail

IFACE=${1:-wlan0}
PORTAL_IP=${2:-127.0.0.1}

echo "Starting Chaos Lab Setup on interface $IFACE"

# 1. Traffic Control (tc)
# Add 30% packet loss and 200ms delay to simulate terrible airport WiFi
echo "Injecting packet loss and delay..."
tc qdisc add dev "$IFACE" root netem loss 30% delay 200ms || {
    echo "tc rule already exists, replacing..."
    tc qdisc change dev "$IFACE" root netem loss 30% delay 200ms
}

# 2. iptables Redirection
# Redirect all port 80 traffic to the fake portal
echo "Injecting DNS/HTTP redirection to Fake Portal ($PORTAL_IP)..."
iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination "$PORTAL_IP:8080" || true

echo "Chaos Lab Active. Run teardown_chaos.sh to revert."
