---
name: browser-display
description: Provide a remote view of the Pi's Chromium desktop via TigerVNC + websockify + noVNC + Tailscale Funnel. Used by any skill that needs to show David a browser screen.
ownership: collab
version: 2.0.0
author: Araminta
---

# Browser Display Skill

## What it does
Exposes the Pi's Chromium desktop (running on DISPLAY :99) as a web-accessible URL via TigerVNC + websockify + noVNC + Tailscale Funnel. David opens the URL in any browser and sees/interacts with Chromium directly.

## URL
The canonical URL is written to `~/.hermes/browser/vnc-url.txt` on startup. Read this file at runtime rather than hardcoding. The pattern is:
```
https://<tailscale-hostname>/<funnel-path>/vnc_lite.html?path=<path>%2F
```

### Correct URL construction

The URL has **two separate path parameters** that must NOT be conflated:

**CRITICAL BUG DISCOVERED MAY 2026:** noVNC's `vnc_lite.html` constructs the WebSocket URL using **only** `window.location.hostname` + the `path` query parameter. It **completely ignores** `window.location.pathname` (the funnel prefix `/browser`).

| URL component | Value | Why it matters |
|---------------|-------|----------------|
| Page path: `/browser/vnc_lite.html` | **Tailscale Funnel prefix** — match live `sudo tailscale funnel status` output. | Routes the HTTPS GET request to websockify on port 6081. |
| Query param: `?path=browser%2Fwebsockify%2F` | **WebSocket endpoint including funnel prefix** — NOT just `websockify`. | Because noVNC builds `wss://host/browser/websockify/`; without the prefix, the WS request hits `/websockify` which Tailscale does not route to the funnel, causing "Loading" forever. |

**Correct formula for path-based funnel (e.g. `/browser`):**
```
https://<tailscale-hostname>/browser/vnc_lite.html?path=browser%2Fwebsockify%2F
```

**Why this works:**
1. Tailscale routes `GET /browser/vnc_lite.html` → websockify serves the HTML page.
2. noVNC reads `path=browser/websockify/` and constructs `wss://host/browser/websockify/`.
3. Tailscale routes the WebSocket upgrade `GET /browser/websockify` → websockify proxies to localhost:5900.

**WRONG formula (causes infinite "Loading"):**
```
https://<tailscale-hostname>/browser/vnc_lite.html?path=websockify%2F
```
- noVNC constructs `wss://host/websockify` — no `/browser` prefix.
- Tailscale funnel is only registered for `/browser/*`, so `/websockify` is not proxied → 404 → noVNC shows "Loading" forever.

**Old incorrect documentation** (pre-May 2026, now fixed): The skill formerly stated `path=websockify%2F` was correct. It was not. The session on 23 May 2026 demonstrated 2+ hours of VNC downtime because the wrong formula was used after the funnel was re-created.

**Separate paths for separate stacks:**
- `/browser` — host Pi TigerVNC + Chromium (this skill).
- `/pirate` — pirate-dock Docker container (VPN container, separate skill).
The two prefixes are NEVER interchangeable.

### URL verification procedure — BEFORE telling David

```bash
# 1. Get the live funnel prefix (do NOT trust vnc-url.txt)
sudo tailscale funnel status | awk '/|--/ && /proxy/ {print $2}'

# 2. Build the correct URL: funnel prefix goes in BOTH the page path AND the path parameter
# Pattern: https://<host>/<funnel-prefix>/vnc_lite.html?path=<funnel-prefix>%2Fwebsockify%2F
# Example:  https://araminta.taild3f7b9.ts.net/browser/vnc_lite.html?path=browser%2Fwebsockify%2F

# 3. Verify noVNC HTML loads via that prefix
curl -s -o /dev/null -w "%{http_code}" "https://<host>/<funnel-prefix>/vnc_lite.html?path=<funnel-prefix>%2Fwebsockify%2F"
# Expected: 200

# 4. Verify websocket upgrade works (locally on Pi)
# websockify expects a raw WS upgrade, not HTTPS - test locally
curl -v -H "Upgrade: websocket" -H "Connection: Upgrade" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://localhost:6081/websockify | grep -c "101"
```

**Do NOT send David a URL until steps 1–3 pass.** The file `~/.hermes/browser/vnc-url.txt` is a hint — always verify against the live funnel state.

## Stack
```
Xtigervnc :99 (X server + VNC server) → Chromium (headed, CDP :9222) → websockify (:6081) → noVNC HTML5 → Tailscale Funnel (/browser → :6081)
```

## Service
Managed by `hermes-browser.service` (systemd user unit).
```bash
systemctl --user status hermes-browser.service
systemctl --user restart hermes-browser.service
```

## Funnel management
Turn on/off as needed (funnel exposes port publicly):
```bash
# Enable
sudo tailscale funnel --bg --https=443 --set-path=/browser 6081
# Disable
sudo tailscale funnel --https=443 --set-path=/browser off
# Check
sudo tailscale funnel status
```

## Startup script
`~/.hermes/browser/scripts/start-browser-stack.sh` — TigerVNC → Chromium → websockify + noVNC.
`~/.hermes/browser/scripts/stop-browser-stack.sh` — kills all processes.

A known-good template is maintained at `templates/start-browser-stack.sh` in this skill directory. Copy it when creating a fresh install or after a destructive change.

For full diagnostic history of the x11vnc→TigerVNC migration, see `references/x11vnc-tigervnc-wayland.md`.

## Pitfalls — DO NOT REPEAT

1. **x11vnc is unusable on Raspberry Pi OS Bookworm.** See `references/x11vnc-tigervnc-wayland.md` for the full diagnostic history. Short version: x11vnc 0.9.16 hard-exits with "Wayland display server detected" regardless of `env -i`, socket removal, or environment stripping. **Use TigerVNC (`Xtigervnc`) instead.** It acts as both X server and VNC server, requires no Xvfb, and has no Wayland issues.
2. **xpra 3.1 (Ubuntu 22.04) is broken for HTML5 WebSocket.** Both `shadow` and `start` modes fail with "server error error accepting new connection" after the WebSocket upgrade handshake succeeds. The raw HTTP→WS upgrade works (101 Switching Protocols) but xpra's application-layer protocol rejects the client. Use TigerVNC + websockify + noVNC instead on 22.04. xpra may work on newer Ubuntu (24.04+).
3. **noVNC URL: use `vnc_lite.html`, not `vnc.html`.** `vnc.html` doesn't handle the `path` parameter correctly for Funnel routing. `vnc_lite.html?path=websockify%2F` connects the WebSocket through the Funnel path prefix. Always test the exact URL with a real browser.
4. **Docker image self-containment: copy files, never symlink.** Symlinks create host-machine dependencies that break when rebuilt on different machines. Always `rm` the symlink then `cp` the real file, or use `cp -L` to resolve the link. The image must build identically on any architecture.
4. **noVNC WebSocket `path` parameter is the internal websockify endpoint, NOT the funnel prefix.** The `?path=websockify%2F` parameter tells noVNC to connect its WebSocket to `wss://host/<funnel-prefix>/websockify` — the websockify server handles `/websockify` internally, while Tailscale routes the outer HTTPS request via the funnel prefix. Do not set `path=` to the funnel prefix; that creates a double-prefix (`/browser/browser`) that websockify rejects with 404.

## Verification
```bash
# Check all ports
ss -tln | grep -E "5900|6081|9222"
# Should show 5900 (TigerVNC), 6081 (websockify), and 9222 (Chromium CDP)

# Test CDP
curl -s http://localhost:9222/json/version | python3 -m json.tool | head -5

# Check TigerVNC logs
[[ -f ~/.hermes/browser/logs/tigervnc.log ]] && tail -3 ~/.hermes/browser/logs/tigervnc.log
```

## Notes
- This is the **canonical** method for providing David a remote browser view.
- All skills (Amazon, etc.) should use this URL pattern.
- **Do not confuse this with pirate-dock's display.** Pirate-dock runs its own noVNC stack inside a Docker container with funnel path `/pirate`. Browser-display is the host Pi's stack with funnel path `/browser`. They share port 6081 and cannot run simultaneously.
- The funnel should be turned off when not actively needed.
- When giving David a VNC URL after fixing a broken one, be explicit about what changed (e.g., "re-registered funnel from /pirate to /browser") so he knows he's trying a different URL.
- **Fallback: Direct VNC via Tailscale.** If the noVNC / websockify / Funnel stack is broken and you cannot fix it quickly, David can connect directly to TigerVNC over Tailscale. See `references/direct-vnc-tailscale-fallback.md` for the full procedure. This is the reliable escape hatch when the web stack misbehaves — David's instruction was explicit: *"show me the fucking screen"* means stop debugging and show the screen, any way possible.