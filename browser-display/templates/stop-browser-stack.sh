#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM=99
CHROME_CDP_PORT=9222
VNC_PORT=5900
WEBSOCKIFY_PORT=6081

echo "Stopping Hermes Browser Stack..."

pkill -f "Xtigervnc :${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "chromium.*remote-debugging-port=${CHROME_CDP_PORT}" 2>/dev/null || true
pkill -f "x11vnc.*:${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "Xvfb :${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "websockify.*${WEBSOCKIFY_PORT}" 2>/dev/null || true
pkill -f "xpra.*:${DISPLAY_NUM}" 2>/dev/null || true

sleep 1
echo "Hermes Browser Stack stopped."
