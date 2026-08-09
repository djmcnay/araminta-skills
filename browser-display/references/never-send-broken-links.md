# Never Send a Broken Link — Session Lesson

## What happened (May 2026)

David asked for the VNC link to complete an Amazon return manually. The file `~/.hermes/browser/vnc-url.txt` contained a legacy URL with path prefix `/browser`:

```
https://araminta.taild3f7b9.ts.net/browser/vnc_lite.html?path=browser%2F
```

David typed this URL and immediately got "This site can't be reached."

David's reaction: *"NEVER, EVER SEND ME A BROKEN LINK... check it first. If there is a legacy skill leading to a broken link.. delete the fucking thing and stop wasting my time"*

## Root cause

The Tailscale Funnel path prefix had drifted from `/browser` to `/pirate` at some point between startup and the current conversation. The static `vnc-url.txt` file was stale. The deeper cause was cross-contamination: `pirate-dock` (a separate Docker-based skill for VPN-specific work) had registered `/pirate` on port 6081, overwriting the `/browser` registration that browser-display relies on. `/pirate` is pirate-dock's path and must never be used for browser-display unless David explicitly says so.

## The rule: verify BEFORE sending

For any URL given to David:

1. **If it's a local service URL** (VNC, noVNC, web UI on the Pi): `curl -s -o /dev/null -w "%{http_code}" http://localhost:<port>` from the Pi itself.
2. **If it's a Tailscale Funnel URL**: `sudo tailscale funnel status` to confirm the path prefix matches.
3. **If it's a Tailscale Funnel URL AND uses noVNC**: `curl -s "https://HOST/path/vnc_lite.html?path=path%2F" | head -3` from the Pi.
4. **Never construct URLs from stale config files alone.** Always verify against live state.

## Verification checklist (mandatory before giving David a URL)

| URL type | Verification command | Expected result |
|----------|---------------------|----------------|
| VNC/noVNC local | `curl -s http://localhost:6081/vnc_lite.html \| head -1` | `<!DOCTYPE html>` |
| VNC/noVNC via Funnel | `curl -s "https://HOST/path/vnc_lite.html?path=path%2F" \| head -1` | `<!DOCTYPE html>` |
| Browser CDP API | `curl -s http://localhost:9222/json/version \| head -5` | JSON with version |
| Direct VNC | `ss -tln \| grep 5900` | Port 5900 LISTEN |
| websockify | `ss -tln \| grep 6081` | Port 6081 LISTEN |
| Tailscale Funnel | `sudo tailscale funnel status` | Shows active paths |

## Self-correction workflow

When you find a broken/stale URL:
1. Immediately verify the live state with `sudo tailscale funnel status`
2. Update `~/.hermes/browser/vnc-url.txt` with the corrected URL
3. Give David the corrected URL — with an explicit note that you verified it
4. Patch the relevant skill to prevent the drift recurring

## The principle: David's time is more valuable than your convenience

A broken link costs David 30-60 seconds of typing, testing, and frustration. Verification costs you 5 seconds. The ratio is unacceptable. Verify first, send second, always.
