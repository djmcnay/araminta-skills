# Funnel Path URL Drift — Session Discovery

## What happened (May 2026)

David asked for the VNC URL to view the Amazon return page. The file `~/.hermes/browser/vnc-url.txt` contained a stale URL.

Investigation showed the **actual Tailscale Funnel registration had drifted**:

```bash
$ sudo tailscale funnel status
https://araminta.taild3f7b9.ts.net (Funnel on)
|-- /       proxy http://127.0.0.1:9119
|-- /hermes proxy http://localhost:9119
|-- /pirate proxy http://localhost:6081
```

`/pirate` is the pirate-dock Docker container (VPN), **not** browser-display.

## Phase 2: The noVNC path parameter bug (23 May 2026)

David reported VNC showed "Loading" indefinitely. After restoring `/browser` as the funnel prefix, the issue persisted.

**Root cause:** noVNC's `vnc_lite.html` constructs the WebSocket URL using **only** `window.location.hostname + '/' + path_query_param`. It **completely ignores** `window.location.pathname` (the funnel prefix `/browser`).

| URL component | What noVNC sees | What it builds |
|---------------|-----------------|----------------|
| Page: `https://host/browser/vnc_lite.html` | Host = `host` | — |
| Query: `?path=websockify%2F` | Path = `websockify/` | `wss://host/websockify/` |

`wss://host/websockify/` → Tailscale funnel only routes `/browser/*` → 404 → infinite "Loading"

## Correct URL pattern (post-23-May-2026)

```
https://<tailscale-hostname>/browser/vnc_lite.html?path=browser%2Fwebsockify%2F
```

The funnel prefix `/browser` must be included in the `path` query parameter:
- noVNC builds `wss://host/browser/websockify/`
- Tailscale routes `/browser/*` to websockify on port 6081
- Websockify handles `/websockify` internally and proxies to TigerVNC
- Connection succeeds

## Why this matters

David's frustration was immediate and severe: *"NEVER, EVER SEND ME A BROKEN LINK... check it first"* and later *"show me the fucking screen."*

The `vnc-url.txt` file is a hint, not a guarantee. Always verify against live funnel state.

## Critical distinction: `/browser` vs `/pirate`

- **`/browser`** → browser-display skill (this skill). Standard VNC to Pi's Chromium desktop.
- **`/pirate`** → pirate-dock skill only. VPN Docker container. **NEVER** use for browser-display unless David explicitly instructs.

## Verification checklist

| Check | Command |
|-------|---------|
| VNC server listening | `ss -tln \| grep 5900` |
| websockify listening | `ss -tln \| grep 6081` |
| noVNC serving HTML | `curl -s http://localhost:6081/vnc_lite.html \| head -3` |
| Funnel active path | `sudo tailscale funnel status` |
| Full end-to-end | `curl -s "https://HOST/<prefix>/vnc_lite.html?path=<prefix>%2Fwebsockify%2F" \| head -3` |

## Direct VNC fallback

If the web stack is broken beyond quick repair, use the direct VNC connection documented in `references/direct-vnc-tailscale-fallback.md`. Sometimes bypassing websockify/noVNC entirely and connecting a native VNC client directly to the Pi's Tailscale IP is the right answer.
