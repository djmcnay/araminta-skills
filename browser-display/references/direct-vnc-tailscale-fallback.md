# Direct VNC Connection via Tailscale — Fallback Method

## What happened (23 May 2026)

David asked to see the Amazon return screen. The standard `browser-display` stack (websockify + noVNC + Tailscale Funnel) was broken: websockify returned 404 for WebSocket upgrade requests, even though noVNC HTML loaded correctly. After 15+ minutes of debugging, David showed frustration: *"show me the fucking screen."*

## The fallback: connect directly via VNC protocol over Tailscale

Since TigerVNC (`Xtigervnc`) on the Pi listens on all interfaces (`-localhost no`) with no password (`-SecurityTypes=None`), and Tailscale provides a secure tunnel, the simple solution is to **bypass the entire websockify/noVNC/Funnel stack** and connect a VNC client directly to the Pi's Tailscale IP.

### What you need

1. **TigerVNC must be running and accessible externally**
   - Verify: `ss -tln | grep 5900` should show port 5900 LISTENING on `0.0.0.0` (not just `127.0.0.1`)
   - The TigerVNC command must include `-localhost no` — otherwise it only listens on loopback and is unreachable via Tailscale
   - Verify: `ps aux | grep 'Xtigervnc'` — look for `-localhost no -SecurityTypes=None -rfbport 5900`

2. **Get the Pi's Tailscale IP**
   ```bash
   tailscale ip --4
   ```
   (e.g., `100.65.212.67`)

3. **Verify VNC port is reachable**
   ```python
   import socket
   s = socket.socket()
   s.connect(('100.65.212.67', 5900))
   s.send(b'RFB 003.003\n')
   resp = s.recv(12)
   print(resp)  # Should print: b'RFB 003.008\n'
   s.close()
   ```

### Instructions for David

Use any VNC client on your Mac (or other device):
- **Screen Sharing** (built-in): `cmd+space` → "Screen Sharing" → enter `vnc://100.65.212.67:5900`
- **RealVNC Viewer**
- **TigerVNC Viewer**

**No password needed.**

### Advantages over noVNC
- No websockify, no noVNC, no HTTPS/TLS, no funnel path confusion
- Direct VNC protocol over Tailscale's encrypted WireGuard tunnel
- Works even when the web stack (websockify, noVNC HTML, Tailscale Funnel) is misconfigured
- Performance: native VNC viewer is typically more responsive than browser-based noVNC

### Limitations
- Requires a native VNC client (not just a web browser)
- Works over Tailscale network only (not "any web browser")
- Requires TigerVNC to be running with `-localhost no` (security note: this is safe because the Tailscale interface is encrypted and authenticated by Tailscale, but do not expose port 5900 to the public internet)

## When to use direct VNC vs noVNC

| Scenario | Use | Why |
|----------|-----|-----|
| David just needs to see the screen quickly | Direct VNC fallback | Faster, fewer moving parts |
| David is on a device without a VNC client | noVNC (if working) | Browser-only, no install |
| websockify is broken / debugging the stack | Direct VNC fallback | Bypass broken component |
| Multiple people need to view simultaneously | noVNC (if working) | HTTP is stateless per client |

## Permanent fix: consider a systemd healthcheck

The websockify 404 failure is a known recurring issue. Direct VNC works as a reliable fallback. A longer-term fix would be to run websockify under systemd with a healthcheck, or to always keep a `browser-display-alt.path` reference file documenting the direct Tailscale VNC IP.
