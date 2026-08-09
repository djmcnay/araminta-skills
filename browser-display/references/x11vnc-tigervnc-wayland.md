# x11vnc vs TigerVNC on Raspberry Pi OS Bookworm

## The Problem

Raspberry Pi OS Bookworm uses `labwc` (a Wayland compositor) as its default desktop session. This creates a Wayland socket at `/run/user/1000/wayland-0`.

x11vnc 0.9.16 (the version in Debian Bookworm / Raspberry Pi OS) has a hard-coded Wayland detection check. On startup it looks for:
- The `WAYLAND_DISPLAY` environment variable
- The actual socket file `/run/user/$UID/wayland-0`

If either is present, it exits immediately with:
```
Wayland display server detected.
Wayland sessions are as of now only supported via -rawfb and the bundled deskshot utility. Exiting.
```

## Attempted Fixes That FAILED

All of these were attempted and all failed:

1. **`env -i` with stripped environment**: x11vnc still detected Wayland. The binary likely checks for the socket file directly, not just environment variables.
2. **Moving the Wayland socket aside before launch**: Even with the socket physically moved to a backup name, x11vnc still detected "Wayland display server." It may check `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, or some other system state.
3. **`env -u WAYLAND_DISPLAY`**: Same result.
4. **Setting `XDG_SESSION_TYPE=x11`**: Same result.

The root cause appears to be that x11vnc 0.9.16 has a compile-time or runtime check that goes beyond simple env var / socket inspection. It may check the current desktop session type through D-Bus, systemd, or some other mechanism.

## The Working Solution: TigerVNC

**TigerVNC** (`Xtigervnc`) is a VNC server that also acts as a full X server. It does NOT depend on an existing X display — it creates one. This means:

- No Xvfb needed (Xtigervnc IS the X server)
- No x11vnc needed (Xtigervnc has built-in VNC)
- No Wayland interaction whatsoever
- Works cleanly on Pi OS Bookworm

Command:
```bash
Xtigervnc :99 -geometry 1280x800 -depth 24 -rfbport 5900 -SecurityTypes=None -localhost no
```

Note: The `-rfbwait` flag is NOT valid for Xtigervnc — it causes a fatal error. Do not include it.

## Stack Comparison

### Old (broken):
```
Xvfb :99 → x11vnc :99 :5900 → websockify :6081 → noVNC → Funnel
```

### New (working):
```
Xtigervnc :99 (X server + VNC on :5900) → websockify :6081 → noVNC → Funnel
     ↑
Chromium (DISPLAY=:99, CDP on :9222)
```

## Reference: Corrected Startup Script

See `templates/start-browser-stack.sh` in this skill directory.

## Key Differences from Old Script

1. No Xvfb — Xtigervnc is the X server
2. No x11vnc — Xtigervnc handles VNC
3. No Wayland socket manipulation needed
4. No `env -i` shenanigans
5. Chromium uses `DISPLAY=:99` directly against Xtigervnc
6. Port 5900 comes up immediately; 6081 and 9222 follow

## Related: RealVNC Incompatibility

Raspberry Pi OS also ships RealVNC Server 7.x which uses RFB 5.x protocol, incompatible with noVNC (which needs RFB 3.8). Do not try to use RealVNC as a substitute.

## Logs
- TigerVNC: `~/.hermes/browser/logs/tigervnc.log`
- Chromium: `~/.hermes/browser/logs/chromium.log`
- websockify: `~/.hermes/browser/logs/websockify.log`
- Combined: `~/.hermes/browser/logs/browser.log`

## Pitfall: Bash `$(id - u)` spacing
A subtle but fatal bug: `$(id - u)` (with a space between `-` and `u`) passes two arguments to `id`, causing it to look up nonexistent users "-" and "u". The command fails silently because of `set -euo pipefail` and `|| true` on the previous line. **Always use `$(id -u)` (no space).**

This caused the script to silently skip the Wayland socket move check and proceed with x11vnc, which then died. The script kept running because `wait` on a dead child doesn't trigger `set -e`.

## Technique: Using strace to diagnose binary startup failures
When a binary silently exits with no useful log, use `strace` to see what files it checks:

```bash
strace -e trace=file,process -f timeout 3 <binary> 2>&1 | grep -E 'access|stat|openat' | head -20
```

Applied here to discover that x11vnc checks the Wayland socket even after `env -i` and physical removal. The strace output showed no file access at all — confirming the detection is hard-coded in the binary itself, not file-system-based.
