# Browser Tools vs Amazon — Session Notes

## The browser_navigate / browser_cdp split

Hermes has two browser tool families that operate on entirely different browser processes:

| Tool | Browser | Cookie persistence | Login state | Use for Amazon |
|------|---------|-------------------|-------------|----------------|
| `browser_navigate`, `browser_click`, `browser_snapshot` | **Camoufox** (fresh, anti-fingerprint) | None per session | None | ❌ NEVER for basket/order/returns |
| `browser_cdp` with `Target.createTarget` | **Persistent Chromium** (port 9222) | Full (the user's Chrome profile) | Preserved | ✅ Always for basket/order/returns |

**Do not mix them in one workflow.** If you `browser_navigate` to a product page and then try to `browser_cdp` into the same tab, you are talking to a different browser. The CDP call will find a tab with a similar URL but it is NOT the tab you just navigated to.

## Amazon accessibility tree limitations

Amazon's product page accessibility tree (what `browser_snapshot` exposes) does NOT reliably include the real buying widget elements:
- The `input#add-to-cart-button` is nested inside Amazon's AUI buying widget and is not exposed as an interactive ref.
- `@e19` in the accessibility tree is a **keyboard shortcut list item** ("Add to basket, shift, ALT, K"), not a clickable DOM element. `browser_click` on it fires the shortcut handler, not the actual add-to-cart AJAX.
- The real button may be discoverable via JavaScript `document.querySelector('#add-to-cart-button')` but clicking it via `Runtime.evaluate` (`.click()` or simulated mouse events) still fails because Amazon's JS pipeline expects a genuine pointer event from a real input device.

**Practical rule:** Do not attempt to add-to-cart via browser automation at all unless using the dedicated Playwright script (`amazon-basket-cli.js` or `amazon/scripts/amazon-returns-cli.js`). For ad-hoc basket additions, send the user the direct link.

## Legacy add-to-cart URL

`https://www.amazon.co.uk/gp/aws/cart/add.html?ASIN.1={ASIN}&Quantity.1=1`

- Loads a confirmation page titled "Amazon.co.uk: Please confirm your action"
- Does NOT silently add to basket — requires a second confirmation click
- May work in some sessions, may not. Not reliable enough to depend on.
- Use only as a last resort, and do not claim success unless the basket count actually increments.

## Verifying the right product (ASIN check)

Before any basket attempt:
1. Confirm the ASIN from search matches the exact product variant the user wants.
2. On the product page, check `document.querySelector('h1')?.innerText` — it should contain the variant keywords ("Mini" vs "Long Range", etc.).
3. If the title doesn't match, the ASIN is wrong. Stop and find the correct one via web search before proceeding.

## Anti-bot detection on return flow final confirmation

**Finding (May 2026):** The Amazon returns flow uses anti-bot detection on the final "CONFIRM YOUR RETURN" step (carrier confirmation page at `/returns/contract/...`). Synthetic click detection is aggressive here — more so than the earlier steps.

### What works
- `browser_cdp` with `Runtime.evaluate` to set form values (reason dropdown, comment textarea, acknowledgement checkbox) — these are data entry steps and are not bot-protected.
- Mouse event dispatch (`Input.dispatchMouseEvent`) for the "items-section-continue" and "resolutions-section-continue" steps — these advance to the refund and carrier pages.

### What does NOT work
- Clicking the final "CONFIRM YOUR RETURN" button via `Runtime.evaluate` `.click()` — Amazon detects the synthetic click and redirects the tab to the Amazon homepage.
- Playwright `locator.click()` or `page.mouse.click()` connected over CDP — same detection, same redirect.
- Setting `force=True` or `dispatchEvent(new MouseEvent('click'))` — all synthetic events are detected.

### The boundary rule
Once the return flow reaches the carrier confirmation page (Post Office/Evri/ASDA selected, refund method chosen), **STOP automation**. The return is ready for the user to do the final click. He can either:
1. Use a VNC link to the Pi's desktop to see the live headless browser and click the button manually.
2. Open the return contract URL in his own browser (already logged in as his Amazon account).

Do not waste time trying synthetic click variants. Amazon's detection is tuned for this exact pattern. Present the contract URL to the user and let him confirm.

## Persistent Chromium quick-start

```
# Verify it's running
ps aux | grep chrom | grep remote-debugging-port=9222

# Create a new tab via CDP
browser_cdp(method="Target.createTarget", params={"url": "https://www.amazon.co.uk/dp/ASIN"})
# -> returns target_id

# All subsequent interaction uses that target_id
browser_cdp(method="Runtime.evaluate", params={"expression": "..."}, target_id="...")
```

Never use `browser_navigate` in the same workflow.
