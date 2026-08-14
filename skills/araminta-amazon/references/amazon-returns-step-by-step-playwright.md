# Amazon Returns — Step-by-Step Browser Automation Guide

## Session provenance
23 May 2026 — BrosTrend AX900 Mini Linux WiFi Dongle (order 203-0317442-4612374), return reason RO_CR-NOT_COMPATIBLE.
the user explicitly asked for **step-by-step** execution: stop after each major step, wait for his "continue" before proceeding.

## Working execution method: Playwright over CDP

When the user asks for live step-by-step browser automation (not Kanban dispatch), use this Playwright-over-CDP pattern:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    cdp_browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = cdp_browser.contexts[0]
    page = None
    for pg in ctx.pages:
        if "amazon.co.uk" in pg.url or "returns" in pg.url:
            page = pg
            break
    if not page:
        print("No Amazon tab found")
        exit(1)
    # page is now the live browser on the persistent Chromium
```

This connects to the SAME logged-in Chromium that the user sees via VNC, so:
- Login state is preserved
- He sees real-time page changes
- Each step is visible to him visually

## Step-by-step return flow (verified working)

### Step 1: Navigate to Order History
```python
page.goto("https://www.amazon.co.uk/gp/css/order-history")
page.wait_for_load_state("domcontentloaded")
```
- No direct order-details URL — Amazon blocks it (`ERR_BLOCKED_BY_RESPONSE`)
- Order history is the safe entry point

### Step 2: Search for order
```python
page.goto("https://www.amazon.co.uk/your-orders/search?opt=ab&search=203-0317442-4612374")
# Or type into #searchOrdersInput if search box is visible
```

### Step 3: Click "View order details"
```python
view_btn = page.get_by_text("View order details").first
view_btn.click()
```

### Step 4: Click "Return items"
```python
return_link = page.locator('a[href*="spr/returns/cart"]').first
return_link.click()
# Result: opens /spr/returns/cart?orderId=...
```

### Step 5: Select item checkbox
```python
checkboxes = page.locator('input[type="checkbox"][id*="self_serviceable"]').all()
for cb in checkboxes:
    cb.check()
```

### Step 6: Select reason
```python
reason_select = page.locator('select[id*="native-dropdown"]').first
reason_select.select_option('RO_CR-NOT_COMPATIBLE')
page.wait_for_timeout(1000)
```
- `select_option()` followed by `dispatchEvent('change')` is NOT needed — Playwright's `.select_option()` already triggers events correctly on `<select>` elements.
- This was confirmed live on the Amazon returns page.

### Step 7: Fill comment
```python
# The textarea ID is conditional on the selected reason code.
# After selecting 'RO_CR-NOT_COMPATIBLE', find the visible textarea:
textarea = page.locator('textarea[id*="RO_CR-NOT_COMPATIBLE"]').first
# Or more broadly:
textarea = page.locator('textarea:visible').locator('[placeholder*="what\'s wrong"]').first

textarea.fill("Wireless dongle never enumerated on Raspberry Pi. AIC8800 chipset incompatible with Pi OS kernel.")
```
**Important:** There are MANY hidden textareas on this page (one per reason code, plus Rufus AI). Only the one matching the selected reason code is `:visible`. Using `[id*="RO_CR-NOT_COMPATIBLE"]` targets the right one directly.

### Step 8: Click Continue to refund page
```python
# The "Continue" button is a span with id ending in "items-section-continue-button-announce"
cont = page.locator('[id*="items-section-continue-button-announce"]').first
cont.click()
page.wait_for_timeout(3000)
# Page advances to /returns/contract/{uuid}
```

### Step 9: Refund method + acknowledgement
```python
# Default (Amazon account balance) is already selected
# Check acknowledgement checkbox
ack = page.locator('[id$="-acknowledgementId"]').first
ack.check()

# Click refund Continue
refund_cont = page.locator('[id*="resolutions-section-continue-button-announce"]').first
refund_cont.click()
page.wait_for_timeout(3000)
```

### Step 10: Carrier selection — CRITICAL PITFALLS

**Pitfall A: Carrier options are COLLAPSED by default**
The carrier page shows only ONE initially selected option (usually Post Office with branch chooser). Simpler carriers (Evri Drop Off, Royal Mail Drop Off, ASDA no-box/no-label) are hidden under a **"2 OTHER RETURN OPTIONS"** collapsed section.

Do NOT try to expand this via text matching — the section includes invisible placeholder divs that also match "OTHER RETURN OPTIONS". Clicking wrong elements can cause the page to rebuild and lose state.

**Better approach when the user wants a simple carrier:**
- If Post Office branch chooser is selected and the user prefers a simpler option, look for the "2 OTHER RETURN OPTIONS" link/button and click it using a precise selector (e.g., `a[href="#"]:has-text("2 OTHER RETURN OPTIONS")` or force=true click).
- The expanded options typically show:
  - ASDA Store — no box or label needed (simplest)
  - Evri Drop Off
  - Royal Mail Drop Off — Box required, no label needed
- Each of these activates "CONFIRM YOUR RETURN" WITHOUT requiring branch selection.

**Pitfall B: Post Office branch chooser "click here" trap**
When Post Office is selected and "Choose drop-off location" is clicked, a modal appears with branch results. The modal contains a **"click here"** link that is NOT a branch selection button — it opens `royalmail.com` in a new browser tab, navigates away from Amazon, and effectively kills the return flow. The actual branch selection is done via:
- Postcode input → search → "Dropoff here" button (index-based, first is nearest)
- Day/time selector buttons (e.g., "08:00 - 19:00")

**NEVER click "click here" or text-similar links in the Post Office modal.** Always use the explicit "Dropoff here" button or day/time buttons.

**Pitfall C: React DOM invisibility**
When carrier options are collapsed, their radio buttons and text content are rendered but invisible to Playwright's DOM traversal. Walking parent containers returns empty strings. To identify which radio belongs to which carrier:
```python
# Use JavaScript evaluation to walk from checkbox up to container with text
result = page.evaluate("""
  () => {
    const radios = document.querySelectorAll('input[type="radio"]');
    for (const r of radios) {
      const container = r.closest('div, span, li');
      if (container && container.innerText.toLowerCase().includes('evri')) {
        return {found: true, id: r.id};
      }
    }
    return {found: false};
  }
""")
# Then click that specific radio by ID
```

**Pitfall D: `.check()` vs `.mouse.click()` on carrier radios**
In May 2026 session, `radio.check()` did NOT reliably select the Post Office carrier. Using `page.mouse.click()` at the radio's bounding box center worked.

**the user's preference for step-by-step execution**
When the user asks for step-by-step Playwright execution ("carry on", "next", "continue" per step), explain upfront what the script block does in plain English terms, then execute. Do NOT explain each line of code during execution — "Clicking the items Continue button" is sufficient detail. the user sees the browser screen via VNC and can observe the effect.

**Typical flow when the user wants step-by-step:**
1. "**Step N — [plain English description of action]**"
2. Execute Python/Playwright block
3. Report result succinctly ("Advanced to refund page" / "Still on same page" + relevant state detail)
4. "Waiting for you to say 'continue'"
5. Repeat

### Step 11: Choose drop-off location
```python
# Open drop-off modal
dropoff_btn = page.get_by_text("Choose drop-off location").first
dropoff_btn.click()
page.wait_for_timeout(2000)

# Find postcode input (may not have attributes — filter by position)
inputs = page.locator('input[type="text"]:visible').all()
for inp in inputs:
    name = inp.get_attribute('name') or ''
    ph = inp.get_attribute('placeholder') or ''
    if name != 'field-keywords' and 'Search' not in ph:
        # This is likely the postcode field
        inp.click()
        inp.fill("")
        page.keyboard.type("[postcode]")
        page.keyboard.press("Enter")
        break

page.wait_for_timeout(3000)
# Check: "liphook" should be in page.content()
```

**Key discovery:** The postcode input in the modal has no distinguishing placeholder, aria-label, or name attribute (all empty). It can only be found by filtering OUT the main Amazon search box (`name='field-keywords'`) and selecting the remaining visible text input.

### Step 12: Select drop-off point
```python
# Click first "Dropoff here"
dropoff = page.locator('button:has-text("Dropoff here")').first
# OR
dropoff = page.get_by_text("Dropoff here").first

dropoff.click()
page.wait_for_timeout(2000)
```

### Step 13: STOP — boundary rule

After "Confirm your return" button is visible:
```python
confirm_btn = page.locator('[id*="methods-section-continue-button-announce"]').first
print("Final confirm button visible but NOT clicking — boundary rule")
```

- The final "CONFIRM YOUR RETURN" button is the boundary. Do NOT click it via automation.
- Amazon detects synthetic clicks on this button even with Playwright's native events.
- Clicking it triggers anti-bot → redirect to homepage.

**Options at this point:**
1. **Tell the user to click "Confirm" manually** (he's watching via VNC)
2. **Use the Amazon returns CLI script** (`amazon/scripts/amazon-returns-cli.js`) — may handle the confirm differently
3. **Let the user click in the browser directly**

## Pitfalls learned

1. **"Fan it to the board" means create Kanban and STOP executing.** the user will remind you. Do not start browser automation after creating a Kanban card. (see SKILL.md Mode 7 — the user's correction)
2. **Playwright step-by-step must pause after each major step.** the user wants to review and approve. Do not chain all steps silently. Wait for "continue" / "carry on" / "next" / "go".
3. **Never click Amazon's final Confirm button via automation.** Boundary rule confirmed May 2026 — anti-bot detection on `methods-section-continue-button-announce` is too strong.
4. **The textarea ID includes the reason code.** `textarea[id*="RO_CR-NOT_COMPATIBLE"]` is the reliable selector for the comment field after that reason is selected. Generic `textarea:visible` works too if only one is visible.
5. **`.select_option()` is sufficient.** No manual `dispatchEvent('change')` needed on `<select>` elements with Playwright.
6. **Carrier selection may need `.mouse.click()` instead of `.check()`.** In May 2026 session, `radio.check()` on Post Office carrier did NOT visually select the radio. A native `page.mouse.click()` at the radio's bounding box center worked.
7. **Postcode input in modal has no attributes.** Empty placeholder, empty name, empty aria-label. Find by excluding the main Amazon search box (`name='field-keywords'`).
8. **When the user says "show me the fucking screen," stop ALL browser automation debugging and give him direct VNC access.** Use the direct VNC fallback (Tailscale IP :5900, no password). The web stack may be broken; a native VNC client bypasses websockify/noVNC/Funnel entirely. See `references/direct-vnc-tailscale-fallback.md`.
