# "Show Me the Screen" — When to Stop Debugging and Give the user Direct VNC Access

## What happened (23 May 2026 — Amazon Return)

The Amazon return had reached the final carrier/confirmation page. The return workflow could be partially automated via Playwright-over-CDP, but multiple automated click attempts (CDP Runtime.evaluate, Playwright `.click()`, Playwright mouse coordinate clicks) failed — the page remained on the same URL, or Amazon redirected to the homepage (anti-bot detection).

the user became frustrated after several automation attempts and a stale VNC URL were sent:
*"I'm pissed off now. Start this from the beginning... show me the fucking screen."*

He later clarified the principle directly:
*"isn't the point of doing via the kanban board that you send it to the kanban and are then free'd up?"*

## The lesson: "show me the screen" is a user command

When the user uses language like:
- "show me the "**fucking**" screen" (emphasis: stop debugging, just show it)
- "I'm pissed off now"
- "stop doing X, just show me Y"

**This is a user-mode command, not a request for more debugging.** The correct response is:
1. **Immediately stop attempting browser automation.** No more CDP clicks, no more Playwright scripts, no more "let me try one more thing."
2. **Switch to VNC delivery mode.** Give the user a direct screen connection — via the fallback Tailscale direct-VNC method if the web stack is broken.
3. **Accept that some tasks require human interaction.** The final "Confirm your return" button is the boundary where Amazon's anti-bot detection reliably defeats automation. Acknowledge this and let the user click it himself.
4. **Only after delivering the screen** should you consider whether automation could have succeeded — not before.

## Why this matters for Amazon returns specifically

Amazon's return flow has multiple anti-bot layers:
- **Items/Reason step:** Can be automated via Playwright CDP with native `.click()` (proven 23 May 2026)
- **Refund/Acknowledgement step:** Can be automated via Playwright CDP
- **Carrier selection step:** Can be automated via Playwright CDP
- **"Choose drop-off location" modal:** Requires clicking a button and filling a postcode — may or may not be automatable
- **"Confirm your return" final button:** `browser_cdp` Runtime.evaluate and even Playwright native `.click()` both trigger homepage redirect (anti-bot detection confirmed 23 May 2026)

**The boundary is the "Confirm your return" button.** Always stop before it and hand off to the user via VNC.

## The Kanban principle: fan it and be freed up

When a task is dispatched to Kanban:
- The value is parallelism and autonomy
- You are NOT meant to also execute it live "just to be sure"
- You are NOT meant to spend 20+ minutes debugging the Kanban worker's path
- You ARE meant to create a populated card and move on

If the user then asks to see the screen (because the Kanban task needs manual intervention or because he prefers it), that is a NEW request — treat it as "show me the screen" not as "resume the Kanban automation inline."

## Frustration language as a signal

the user does not get angry often. When he does, treat it as a first-class signal:

| Frustration signal | Meaning | Your action |
|-------------------|---------|-------------|
| "I'm pissed off now" | Previous approach has failed repeatedly | Stop immediately, reset, ask for clean-slate instructions |
| "show me the fucking screen" | Stop debugging the stack, just deliver the screen | Use direct VNC fallback, no more automation attempts |
| "isn't the point of Kanban that..." | You are doing the worker's job instead of dispatching | Stop executing, trust the dispatch system |
| "start this from the beginning" | Previous context is stale/broken | Do not reference prior attempts, start fresh |
| "don't be anchored on previous conversations" | Clean slate preferred | Forget previous approaches, ask what he wants NOW |

## Fallback priority when screen delivery is needed

1. **Canonical noVNC via Tailscale Funnel** (`https://host/browser/vnc_lite.html?path=websockify%2F`) — if working
2. **Direct Tailscale VNC** (`<tailscale-ip>:5900` via native VNC client) — the reliable escape hatch; see `references/direct-vnc-tailscale-fallback.md`
3. **Ask the user to run browser automation himself** — absolute last resort

Never keep the user waiting while you debug websockify or funnel paths. If the canonical path is broken and cannot be fixed in under 30 seconds, use the fallback.
