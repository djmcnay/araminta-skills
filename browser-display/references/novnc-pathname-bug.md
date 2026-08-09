# noVNC ignores window.location.pathname — the URL construction bug

**Session:** 23 May 2026  
**Impact:** 2+ hours of VNC downtime, multiple broken VNC links sent to David.  
**Root cause:** noVNC's `vnc_lite.html` strips `window.location.pathname` when building the WebSocket URL.

## The bug

Look at the built-in noVNC `vnc_lite.html` source (lines 140–162):

```javascript
const host = readQueryVariable('host', window.location.hostname);
let port = readQueryVariable('port', window.location.port);
const path = readQueryVariable('path', 'websockify');

let url;
if (window.location.protocol === "https:") {
    url = 'wss';
} else {
    url = 'ws';
}
url += '://' + host;
if(port) {
    url += ':' + port;
}
url += '/' + path;  // <-- NOTICE: NO pathname included
```

**It uses `window.location.hostname` but NOT `window.location.pathname`.**

So when the page is accessed via `https://araminta.taild3f7b9.ts.net/browser/vnc_lite.html?path=websockify%2F`, noVNC builds the WebSocket URL as:

```
wss://araminta.taild3f7b9.ts.net/websockify
```

...ignoring the `/browser` funnel prefix entirely. Tailscale Funnel is only registered for `/browser/*`, so `/websockify` is not proxied → 404 WebSocket failure → noVNC shows "Loading" forever.

## The fix

The `path` query parameter must include the funnel prefix:

| Funnel prefix | Correct noVNC path param | Wrong path param (causes Loading forever) |
|--------------|--------------------------|-------------------------------------------|
| `/browser` | `path=browser%2Fwebsockify%2F` | `path=websockify%2F` |
| `/pirate` | `path=pirate%2Fwebsockify%2F` | `path=websockify%2F` |

With `path=browser%2Fwebsockify%2F`, noVNC builds:

```
wss://araminta.taild3f7b9.ts.net/browser/websockify
```

...which Tailscale routes correctly because it matches the `/browser` funnel registration.

## Why this was confusing

Before discovering the bug, we assumed `path=websockify%2F` was correct because:

1. websockify internally handles `/websockify` as its WebSocket endpoint.
2. The noVNC documentation does not mention path-based reverse proxies.
3. It likely worked "by accident" in the past when the funnel was on the root path (`/`).

Once the funnel was recreated with `--set-path=/browser`, the old formula silently broke.

## Detection

Symptom: noVNC page loads (HTML 200) but shows "Loading" indefinitely. Browser DevTools → Network → WS tab shows a WebSocket connection that fails with 404.

## Verification

```bash
# Step 1: On the Pi, verify the noVNC HTML page loads through the funnel
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://araminta.taild3f7b9.ts.net/browser/vnc_lite.html?path=browser%2Fwebsockify%2F"
# Expected: 200

# Step 2: Check the live funnel prefix
tailscale funnel status | grep -oP '(?<=\|-- ).+?(?= )'
# Expected: /browser
```

## Escape hatch: direct VNC over Tailscale

If the noVNC/websockify/Funnel stack cannot be fixed quickly, give David the direct VNC address:

```
Host:   100.65.212.67:5900  (Pi's Tailscale IP, TigerVNC port)
Pass:   none (TigerVNC started with -SecurityTypes=None)
```

This bypasses the entire web stack. On macOS: Screen Sharing app → `vnc://100.65.212.67:5900`.
