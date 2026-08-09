#!/usr/bin/env bash
set -euo pipefail

# Hermes Browser Stack — Xtigervnc + Chromium + websockify + noVNC
# TigerVNC acts as both X server and VNC server — avoids x11vnc Wayland issues
# Access via Tailscale Funnel: https://HOSTNAME/browser/vnc_lite.html?path=browser%2F
# Requires: tigervnc-standalone-server, websockify, novnc, chromium

DISPLAY_NUM=99
CHROME_CDP_PORT=9222
CHROME_DATA_DIR="$HOME/.hermes/browser/chrome-profile"
VNC_PORT=5900
WEBSOCKIFY_PORT=6081
LOG_DIR="$HOME/.hermes/browser/logs"
GEOMETRY="1280x800"
VNC_PASSWD="$HOME/.hermes/browser/vnc-passwd"

mkdir -p "$LOG_DIR"

# Cleanup any existing stack
pkill -f "Xtigervnc :${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "chromium.*remote-debugging-port=${CHROME_CDP_PORT}" 2>/dev/null || true
pkill -f "x11vnc.*:${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "Xvfb :${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "websockify.*${WEBSOCKIFY_PORT}" 2>/dev/null || true
pkill -f "xpra.*:${DISPLAY_NUM}" 2>/dev/null || true
sleep 1

# 1. TigerVNC (X server + VNC server in one)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting TigerVNC on :${DISPLAY_NUM} (port ${VNC_PORT})..." | tee -a "${LOG_DIR}/browser.log"
Xtigervnc :${DISPLAY_NUM} \
  -geometry ${GEOMETRY} \
  -depth 24 \
  -rfbport ${VNC_PORT} \
  -SecurityTypes=None \
  -localhost no \
  -AlwaysShared \
  >> "${LOG_DIR}/tigervnc.log" 2>&1 &
TIGERVNC_PID=$!
sleep 2

# Verify TigerVNC started
if ! ss -tln | grep -q ":${VNC_PORT}"; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: TigerVNC did not start on port ${VNC_PORT}" | tee -a "${LOG_DIR}/browser.log"
  cat "${LOG_DIR}/tigervnc.log" | tail -10 | tee -a "${LOG_DIR}/browser.log"
  exit 1
fi

# 2. Chromium (headed, CDP)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Chromium with CDP on port ${CHROME_CDP_PORT}..." | tee -a "${LOG_DIR}/browser.log"
DISPLAY=:${DISPLAY_NUM} chromium \
  --disable-gpu --disable-dev-shm-usage \
  --user-data-dir="${CHROME_DATA_DIR}" \
  --remote-debugging-port=${CHROME_CDP_PORT} \
  --remote-debugging-address=127.0.0.1 \
  --window-size=${GEOMETRY//x/,} \
  --no-first-run --disable-default-apps \
  --disable-popup-blocking --disable-translate \
  "about:blank" \
  >> "${LOG_DIR}/chromium.log" 2>&1 &
CHROME_PID=$!
sleep 3

# 3. websockify — bridges VNC→WebSocket, serves noVNC HTML
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting websockify on port ${WEBSOCKIFY_PORT}..." | tee -a "${LOG_DIR}/browser.log"
if command -v websockify &>/dev/null; then
  # System websockify (Python package)
  websockify "${WEBSOCKIFY_PORT}" "localhost:${VNC_PORT}" \
    --web=/usr/share/novnc \
    --cert=none \
    >> "${LOG_DIR}/websockify.log" 2>&1 &
else
  # Fallback: python3 -m websockify
  python3 -m websockify "${WEBSOCKIFY_PORT}" "localhost:${VNC_PORT}" \
    --web=/usr/share/novnc \
    --cert=none \
    >> "${LOG_DIR}/websockify.log" 2>&1 &
fi
WEBSOCKIFY_PID=$!
sleep 2

# Write working URL to a file for other tools to read
TAILSCALE_HOST=""
if command -v tailscale &>/dev/null; then
  TAILSCALE_HOST="$(tailscale status --json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("Self",{}).get("DNSName","").rstrip("."))' 2>/dev/null || true)"
fi
if [ -n "$TAILSCALE_HOST" ]; then
  cat > "$HOME/.hermes/browser/vnc-url.txt" <<EOF
https://${TAILSCALE_HOST}/browser/vnc_lite.html?path=browser%2Fwebsockify%2F
EOF
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] VNC URL written to vnc-url.txt" | tee -a "${LOG_DIR}/browser.log"
fi

echo ""
echo "=== Hermes Browser Stack Running ==="
echo "  TigerVNC:  localhost:${VNC_PORT}"
echo "  websockify: localhost:${WEBSOCKIFY_PORT} (serves noVNC)"
echo "  CDP:       http://localhost:${CHROME_CDP_PORT}/json"
echo ""

# Wait for any child to exit (ignore failures — service stays up while any child lives)
wait ${TIGERVNC_PID} ${CHROME_PID} ${WEBSOCKIFY_PID} || true
