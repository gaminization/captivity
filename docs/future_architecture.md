# Captivity: Future Architecture Blueprint

Captivity has evolved from a CLI tool into an autonomous, self-healing network daemon. To reach the final frontier of production-grade deployment, the architecture must evolve closer to the kernel and integrate distributed intelligence.

## 1. OS-Level Integration (NetworkManager Plugin)

Instead of running as a standalone Python daemon polling DBus/nmcli, Captivity should become an upstream NetworkManager (NM) plugin.

**Architecture:**
- **Language:** C/C++ or Rust (to link with `libnm`).
- **Hook Point:** Bind directly to NM's `ConnectivityChanged` and `StateChanged` signals via `libnm-glib` API.
- **Benefit:** Zero latency on network changes. Direct access to interface routing tables and DNS configuration. NM can pause other services (like VPNs) until Captivity finishes the portal login, eliminating race conditions.

## 2. Kernel-Adjacent Evolution (Netlink Sockets)

To completely eliminate DBus overhead and polling dependencies, the daemon can subscribe directly to the Linux Kernel's Netlink interface.

**Implementation (rtnetlink):**
- Monitor `RTM_NEWLINK` and `RTM_DELLINK` to detect physical interface (wlan0) state changes.
- Monitor `RTM_NEWROUTE` to detect when a default gateway is assigned.
- **Benefit:** Sub-millisecond reaction times. Captivity knows the network is up before NetworkManager even fully registers it, allowing the portal probe to fire instantly.

## 3. Distributed Intelligence & Telemetry Layer

Captive portals change their HTML and CAPTCHA strategies frequently. A static plugin architecture will eventually bit-rot.

**Architecture:**
- **Telemetry Collection:** When a new portal is encountered, anonymized fingerprints (redirect URL pattern, HTML structure snippet, CAPTCHA provider) are sent to a central intelligence server.
- **Machine Learning Detection:** The server runs clustering algorithms to classify portal vendors (e.g., Cisco ISE, Aruba ClearPass, custom airport portals).
- **Dynamic Updates:** The daemon periodically pulls newly discovered login strategies (plugins) and detection heuristics from the intelligence network, creating a self-updating global immune system against captive portals.

## 4. Formal Verification Expansion (TLA+)

The current TLA+ specification (`formal/Captivity.tla`) proves the state machine's liveness and safety invariants. Future work involves:
- Expanding the model to include concurrency (modeling the network monitor thread independently from the main loop).
- Adding temporal constraints (modeling time delays and exponential backoffs).
- Automatically translating the TLA+ state machine directly into Rust code for the NetworkManager plugin.

## 5. Chaos Lab Infrastructure

The current `chaos_lab` uses `tc` (Traffic Control) and `iptables` DNAT.
- **Future:** Package this as a standalone `pytest-chaos-wifi` plugin.
- Allows developers of *any* network software to easily simulate adversarial airport Wi-Fi conditions during their test suites.
