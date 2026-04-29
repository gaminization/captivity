#!/usr/bin/env bash
# Captivity Chaos Runner
# Randomly toggles interfaces, drops packets, and observes the daemon

set -euo pipefail

IFACE=${1:-wlan0}

echo "Starting Chaos Runner on $IFACE"
echo "Press Ctrl+C to stop."

cleanup() {
    echo "Stopping Chaos Runner..."
    ./teardown_chaos.sh "$IFACE"
    exit 0
}

trap cleanup SIGINT SIGTERM

./setup_chaos.sh "$IFACE"

while true; do
    ACTION=$((RANDOM % 4))
    
    case $ACTION in
        0)
            echo "[Chaos] Taking $IFACE DOWN for 5 seconds..."
            ip link set "$IFACE" down || true
            sleep 5
            echo "[Chaos] Bringing $IFACE UP..."
            ip link set "$IFACE" up || true
            ;;
        1)
            echo "[Chaos] Flushing DNS cache..."
            systemd-resolve --flush-caches 2>/dev/null || true
            ;;
        2)
            echo "[Chaos] Changing netem packet loss to 50%..."
            tc qdisc change dev "$IFACE" root netem loss 50% delay 500ms 2>/dev/null || true
            sleep 10
            echo "[Chaos] Restoring netem packet loss to 30%..."
            tc qdisc change dev "$IFACE" root netem loss 30% delay 200ms 2>/dev/null || true
            ;;
        3)
            echo "[Chaos] Injecting transient iptables DROP rule for 10s..."
            iptables -I OUTPUT -p tcp --dport 80 -j DROP || true
            sleep 10
            iptables -D OUTPUT -p tcp --dport 80 -j DROP || true
            ;;
    esac
    
    # Wait before next chaos event
    sleep $((RANDOM % 15 + 5))
done
