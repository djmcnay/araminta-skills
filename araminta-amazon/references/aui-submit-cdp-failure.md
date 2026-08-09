# Amazon AUI Hidden Submit Input — CDP Failure

## Discovery
**Session:** May 2026, BrosTrend WiFi dongle return (Order 203-0317442-4612374)
**Problem:** Form submission on Amazon return flow via CDP `browser_cdp` + `Runtime.evaluate` clicks the hidden submit input but the page does NOT advance.

## Structure
Amazon AUI "Continue" buttons are implemented as:

```html
<span class="a-button">
  <span class="a-button-inner">
    <input data-form-id="items-section-form-v2" 
           class="a-button-input" type="submit" 
           aria-labelledby="orc-items-section-continue-button-announce">
    <span id="orc-items-section-continue-button-announce" class="a-button-text">
      Continue
    </span>
  </span>
</span>
```

The visible element is `<span id="orc-items-section-continue-button-announce">`.
The actual form submit is `<input type="submit" class="a-button-input">`.

## What fails
Calling `.click()` on the hidden `<input type="submit">` via CDP:
```js
const submit = document.querySelector('input[type="submit"]');
submit.click(); // returns success, form does NOT advance
```

This succeeds (no JS error, no exception) but the server-side form validation rejects it. The page stays on the same URL. Possible causes:
- Hidden inputs with `aria-labelledby` may be ignored by Amazon's event pipeline.
- The form requires pointer events (mouse coordinates) for anti-bot validation.
- CDP Runtime.evaluate executes JS without pointer-event metadata, so Amazon's anti-bot layer discards the submission.

## What works instead
1. **Playwright CLI** (`amazon-returns-cli.js`) — generates real pointer events via `.click()` in a headed/real browser context, not CDP Runtime.evaluate
2. **Manual user click** via VNC → the visible span works because it fires real pointer events
3. **Playwright `connect_over_cdp` with real `.click()`** — this generates OS-level pointer events, not synthetic JS clicks

## Key distinction
| Method | Events | Works for AUI submit? |
|--------|--------|----------------------|
| CDP `Runtime.evaluate` + `.click()` | Synthetic JS only | NO |
| CDP `Runtime.evaluate` + `dispatchEvent(MouseEvent)` | Synthetic JS only | NO |
| Playwright `page.click()` on element | OS-level pointer + JS | YES |
| Real human click via VNC | OS-level pointer + JS | YES |

## Rule
For Amazon return form submission: **do NOT use CDP Runtime.evaluate for the Continue/Submit step**. Use the Playwright CLI script or stop and ask the user to click the button via VNC.

## Verification
After any click attempt, verify advancement by checking `window.location.href` — if unchanged after 3s, the click did not work.
