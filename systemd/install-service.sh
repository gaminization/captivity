#!/usr/bin/env bash
# =============================================================================
# install-service.sh — Deploy Captivity as a user-session systemd service
#
# Must be run as the regular user (NOT root / sudo).
# The user service runs inside the login session, giving it access to:
#   - GNOME keyring / SecretService (D-Bus session bus)
#   - NetworkManager events
#   - DISPLAY / XAUTHORITY for browser fallbacks
#
# Usage:
#   bash install-service.sh [--uninstall]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SRC="${SCRIPT_DIR}/captivity-user.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_DST="${USER_SYSTEMD_DIR}/captivity.service"
AUTOSTART_DIR="${HOME}/.config/autostart"
TRAY_DESKTOP="${AUTOSTART_DIR}/captivity-tray.desktop"
DISPATCHER_SRC="${SCRIPT_DIR}/99-captivity-dispatcher"
DISPATCHER_DST="/etc/NetworkManager/dispatcher.d/99-captivity"

# ── helpers ──────────────────────────────────────────────────────────────────
info()    { echo "  ✓ $*"; }
warn()    { echo "  ⚠ $*" >&2; }
die()     { echo "  ✗ $*" >&2; exit 1; }

# ── uninstall ─────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--uninstall" ]]; then
    echo "Uninstalling Captivity user service…"
    systemctl --user stop  captivity 2>/dev/null || true
    systemctl --user disable captivity 2>/dev/null || true
    rm -f "${SERVICE_DST}" "${TRAY_DESKTOP}"
    systemctl --user daemon-reload
    info "User service removed"
    echo
    echo "To also remove the NM dispatcher (requires sudo):"
    echo "  sudo rm -f ${DISPATCHER_DST}"
    exit 0
fi

# ── sanity checks ─────────────────────────────────────────────────────────────
[[ -f "${SERVICE_SRC}" ]] || die "Service file not found: ${SERVICE_SRC}"
[[ -x "$(command -v captivity)" ]] || die "'captivity' not found in PATH. Run: pip install -e . first."

# ── stop stale system service if running ──────────────────────────────────────
if systemctl is-active --quiet captivity 2>/dev/null; then
    warn "System-level captivity.service is running. Stopping it."
    sudo systemctl stop    captivity || warn "Could not stop system service (sudo needed)"
    sudo systemctl disable captivity || warn "Could not disable system service (sudo needed)"
fi

# ── deploy user service ───────────────────────────────────────────────────────
echo "Installing Captivity user service…"
mkdir -p "${USER_SYSTEMD_DIR}"
cp "${SERVICE_SRC}" "${SERVICE_DST}"
info "Installed ${SERVICE_DST}"

systemctl --user daemon-reload
systemctl --user enable --now captivity
info "User service enabled and started"

# ── enable linger (survive reboot without active login) ───────────────────────
loginctl enable-linger "${USER}" 2>/dev/null && info "Linger enabled for ${USER}" \
    || warn "Could not enable linger — service won't auto-start at boot without an active session"

# ── tray autostart ────────────────────────────────────────────────────────────
mkdir -p "${AUTOSTART_DIR}"
cat > "${TRAY_DESKTOP}" << EOF
[Desktop Entry]
Type=Application
Name=Captivity Tray
Comment=Captivity system tray icon
Exec=${HOME}/.local/bin/captivity tray
X-GNOME-Autostart-enabled=true
EOF
info "Tray autostart installed → ${TRAY_DESKTOP}"

# ── NM dispatcher (optional, requires sudo) ────────────────────────────────────
if [[ -f "${DISPATCHER_SRC}" ]]; then
    echo
    echo "Install NetworkManager dispatcher for instant reconnect events?"
    echo "  sudo cp ${DISPATCHER_SRC} ${DISPATCHER_DST}"
    echo "  sudo chmod 755 ${DISPATCHER_DST}"
    echo "(This is optional but recommended — provides instant re-login on WiFi reconnect)"
fi

# ── status ───────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════"
systemctl --user status captivity --no-pager -l 2>&1 | head -12
echo "═══════════════════════════════════════════"
echo
echo "Done.  Logs: journalctl --user-unit captivity -f"
