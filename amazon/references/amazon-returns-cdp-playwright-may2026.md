# Amazon Returns — CDP vs Playwright Boundary (May 2026 Session)

## Session
BrosTrend AX900 Mini Linux WiFi Dongle return, Order 203-0317442-4612374, May 23 2026.

## Key Finding: Playwright `connect_over_cdp` + native `.click()` works for most steps

The earlier `references/aui-submit-cdp-failure.md` documented that CDP `Runtime.evaluate` synthetic clicks fail on Amazon AUI Continue buttons. This reference refines that finding.

**What actually works:**

| Approach | Items→Reason | Reason→Refund | Refund→Carrier | Carrier→Confirm |
|----------|-----------|-------------|---------------|----------------|
| CDP `Runtime.evaluate` + `.click()` on hidden submit | ❌ No | ❌ No | ❌ No | ❌ No |
| CDP `Runtime.evaluate` + `dispatchEvent(MouseEvent)` on visible span | ❌ No | ❌ No | ❌ No | ❌ No |
| **Playwright `connect_over_cdp` + `.click()` on visible span** | **✅ Yes** | **✅ Yes** | **✅ Yes** | ❌ Triggers bot detection |
| Manual human click via VNC | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |

### Why Playwright CDP works where raw CDP doesn't

Playwright's `.click()` method (even on a CDP-attached page) generates **OS-level pointer events** with coordinates, timestamps, and proper event sequences (`mousedown` → `mouseup` → `click`). Amazon's anti-bot layer validates these metadata and accepts the interaction.

CDP `Runtime.evaluate` executes JavaScript in the page context but produces **synthetic events without pointer metadata** — Amazon's server-side validation rejects them as non-human.

### Verified working code pattern

```python
from playwright.async_api import async_playwright

browser = await p.chromium.connect_over_cdp("http://localhost:9222")
ctx = browser.contexts[0]
# Find existing returns tab OR create new page
page = ...

# Step: Items → Reason
await page.locator('span[id*="orc-items-section-continue-button-announce"]').click()

# Step: Select reason (native select with JS dispatch)
await page.evaluate('''
  () => {
    const sel = document.querySelector('select[id*="native-dropdown"]');
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
    setter.call(sel, 'RO_CR-NOT_COMPATIBLE');
    sel.dispatchEvent(new Event('change', {bubbles: true}));
  }
''')

# Step: Fill comment in the REAL textarea (NOT the Rufus widget)
textareas = await page.locator('textarea').all()
for ta in textareas:
    ta_id = await ta.get_attribute('id') or ''
    if 'rufus' not in ta_id.lower():
        await ta.fill("comment text", force=True)
        await ta.dispatch_event('input')
        await ta.dispatch_event('change')
        break

# Step: Reason → Refund (native Playwright click works!)
await page.locator('span[id*="orc-items-section-continue-button-announce"]').click()

# Step: Refund → Carrier
# Check acknowledgement checkbox if needed
ack = page.locator('input[id*="acknowledgementId"]')
if await ack.count() > 0:
    await ack.check(force=True)
await page.locator('span[id*="resolutions-section-continue-button-announce"]').click()
```

## What does NOT work — confirmed failures

### Native `HTMLFormElement.prototype.submit()`
```js
const form = document.querySelector('form[id*="items-section-form"]');
HTMLFormElement.prototype.submit.call(form);
// Result: Amazon redirects to error page:
// "The Web address you entered is not a functioning page on our site."
// at /spr/returns/resolutions
```

This is indistinguishable from bot-flagged submission. Amazon's server-side validation discards form submissions without proper event metadata.

### Playwright `evaluate("el => el.click()")` on hidden submit input
```python
await page.locator('input[type="submit"]').evaluate("el => el.click()")
# Returns success tuple, page STAYS on same URL
```

Same underlying issue: synthetic JS click lacks pointer-event metadata.

### Playwright `evaluate("el => el.click()")` on the FINAL "Confirm your return" button — CONDITIONAL
This is **NOT** an absolute boundary. It succeeds when the chosen carrier does NOT require a branch-selection modal (e.g. Evri Drop Off, ASDA Store). It fails when the carrier requires choosing a specific branch (Post Office dropdown/chooser, Royal Mail postcode modal) because validation fails before submission.

**Rule:** Choose simple carriers first, then try the submit click. See `references/amazon-returns-carrier-fallback.md` for the full fallback chain.

## Environment note: `AMAZON_RETURNS_HEADLESS=1`

The existing `amazon-returns-cli.js` script launches its own Chromium instance rather than connecting to CDP. When run on a headless Pi (no X11 display), it requires:

```bash
AMAZON_RETURNS_HEADLESS=1 node amazon-returns-cli.js "product name" "reason" /path/to/cookies.json
```

Without the env var:
```
Looks like you launched a headed browser without having a XServer running.
Set either 'headless: true' or use 'xvfb-run <your-playwright-app>' before running Playwright.
```

## Rufus textarea trap

Amazon's return pages contain TWO textareas:
1. **Rufus AI chat widget** (`id="rufus-text-area"`, placeholder="Ask Rufus a question") — NOT for comments
2. **Actual comment textarea** (`id*="AmazonDefault_EULegal"`, no placeholder) — this is the one to fill

Filling the Rufus textarea with return comments will appear to succeed but the form validation will reject the submission because the actual required comment field is empty.

Detection: always iterate `document.querySelectorAll('textarea')` and skip any with `'rufus'` in the id/class.

## Boundary summary for automated Amazon returns

| Step | Can automate? | Method |
|------|--------------|--------|
| Navigate to return cart | ✅ Yes | `page.goto()` |
| Check item checkbox | ✅ Yes | `page.locator('input[type="checkbox"]').check()` |
| Select reason | ✅ Yes | JS `Object.getOwnPropertyDescriptor` + dispatch |
| Fill comment | ✅ Yes | Find real textarea, `.fill()` + dispatch input/change |
| Items Continue → Refund | ✅ Yes | Playwright `.click()` on visible span |
| Refund acknowledgement | ✅ Yes | `page.locator('input[id*="acknowledgementId"]').check()` |
| Refund Continue → Carrier | ✅ Yes | Playwright `.click()` on visible span |
| Select carrier (Post Office) | ✅ Yes | `page.locator('input[type="radio"]').check()` |
| Choose drop-off location | ⚠️ Partial | Modal interaction tricky; may need manual help |
| **Final "Confirm your return"** | **❌ NO** | **Stop here. Bot detection triggers.** |
