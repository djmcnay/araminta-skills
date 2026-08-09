# Amazon Shopping Skill

Browse, shop, and manage returns on Amazon. Supports reorder, fuzzy search, best-value comparison, product research, basket management, and return initiation.

## Capabilities

1. **Reorder (exact)** — find a specific past purchase and reorder it
2. **Reorder-like** — find the cheapest equivalent of a previous purchase (brand + product type must match, variant/size can vary)
3. **Fuzzy search** — find a specific item the user names, even without the full product name or brand
4. **Best Value** — compare pack sizes/variants using unit pricing to find the best deal
5. **Research** — search for a product, compare options, recommend (Amazon-only for commodities; broader internet research for gifts/specialist items)
6. **Basket** — add items to the user's basket for review and manual checkout
7. **Returns** — initiate a return for a past purchase via browser automation

## Hard Guardrails

- **NEVER** place an order, subscribe, or complete a purchase
- **NEVER** complete any action that costs money — the boundary is: basket only. The user completes purchases.
- **NEVER** change account settings (addresses, payment methods, subscriptions, cancellations)
- **NEVER** access or display full card details
- If asked to buy/order: add to basket and tell the user it's ready for review
- If not logged in and basket add fails: send the user the direct product link instead of pretending to have added it
- **NEVER ask the user for an ASIN.** The skill handles all product discovery: searching order history, Amazon search, brand matching, variant comparison, and unit-price calculation.
- Present recommendations and add to basket in one flow. Only ask for clarification on non-obvious or expensive decisions (£50+ or unfamiliar brands).

## Platform

- amazon.co.uk (UK Prime account) — adjust the TLD for other regions
- Uses a persistent browser session (Chromium/Chrome) for logged-in operations
- Anonymous browsing (anti-fingerprint or fresh profiles) for product research only, not for authenticated actions

## Browser Selection — Critical

For any operation requiring login (basket adds, order history, returns):

- **USE A PERSISTENT BROWSER SESSION** with full cookie persistence and a real user profile
- **DO NOT use anti-fingerprint browsers** (e.g. Camoufox) for logged-in operations — anti-bot fingerprinting breaks the XHR/fetch event pipeline behind Amazon's add-to-cart button. The click registers visually, but the basket count does NOT increment.
- Anti-fingerprint browsers are fine for anonymous scraping (product research, price checks, browsing other retailers).
- If available, use a Playwright script connecting to the persistent browser via CDP for basket operations — it generates genuine pointer events. Do not rely on accessibility-tree clicks for add-to-cart.

### browser_navigate vs CDP — different browsers

If your harness has both a high-level browser tool and a low-level CDP tool, they may talk to entirely different browser instances:
- The high-level tool may spawn a separate anti-fingerprint browser (no cookie persistence, not logged in)
- The CDP tool connects to the persistent Chromium (logged in, full cookies)

They do NOT share tabs, sessions, or login state.

**Rule:** For any Amazon operation requiring login, use the persistent browser exclusively. Never mix browser instances in the same workflow.

### Quick test: which browser am I in?

```js
document.body.innerText.includes("Hello, <name>")
// If it shows the user's name you are in the right session
```

Note: `document.querySelector('#nav-link-accountList-nav-line-1')?.innerText` also works but is fragile on some pages (cart, smart-wagon use different header layouts). `body.innerText` is more reliable.

## Key Reference Files

- `references/browser-tools-amazon.md` — browser tool behaviour vs Amazon, accessibility tree limitations
- `references/variant-selection.md` — variant extraction, fuzzy matching, buy-box re-render, what NOT to use
- `references/aui-submit-cdp-failure.md` — why hidden `<input type="submit">` clicks via CDP fail on Amazon AUI forms
- `references/amazon-returns-cdp-playwright.md` — which steps can be automated via Playwright CDP vs requiring human interaction
- `references/amazon-returns-carrier-fallback.md` — carrier fallback chain (Evri → ASDA → Post Office → Royal Mail)
- `references/amazon-returns-step-by-step-playwright.md` — step-by-step Playwright-over-CDP execution pattern
- `references/stop-and-show-screen.md` — when the user says "show me the screen," stop debugging and give direct screen access

## Login and Access

### How to detect login state

When navigating to any Amazon page, check for signs of being logged in:
- **Logged in:** Page shows "Delivering to [location]" with no "Hello, sign in" prominent in header, or order history loads without redirect to sign-in
- **Not logged in:** Sign-in form appears, or header shows "Hello, sign in" / "Account and Lists" points to sign-in

### Primary: Amazon Order History

1. Navigate to `https://www.amazon.co.uk/gp/css/order-history`
2. If already logged in, proceed to order search
3. If login required, fall back to email search for order history, or search Amazon directly for the product

### Basket failures — troubleshooting

**Case A: Not logged in**
- Do NOT claim you've added it to the basket
- Instead, send the user the **direct product link** with the price and a brief description
- Phrase: *"Can't add to basket — not logged in. Here's the link for you to add it yourself:"*

**Case B: Logged in but add-to-cart silently fails**

Symptoms: Header shows the user's name and delivery address, but clicking the add-to-cart button produces no basket increment. The `#nav-cart-count` stays at 0.

Root causes to check in order:
1. **Wrong browser instance** — using an anti-fingerprint browser instead of the persistent one. The click fires in the DOM but the XHR/fetch never reaches Amazon's servers.
2. **Accessibility tree button is a keyboard shortcut, not the real button** — Amazon's accessibility tree exposes a shortcut list item (e.g. "Add to basket, shift, ALT, K"). Clicking this ref clicks the shortcut handler, not the actual buying widget button. The real `#add-to-cart-button` input is nested inside Amazon's buying widget and is NOT reliably exposed through the accessibility tree.
3. **Legacy add-to-cart URL fails** — `https://www.amazon.co.uk/gp/aws/cart/add.html?ASIN.1={ASIN}&Quantity.1=1` may redirect to a confirmation page that requires a follow-up click.

Diagnosis steps:
1. Confirm you're on the persistent browser (check login state and browser instance)
2. Check basket count before any attempt: `document.querySelector('#nav-cart-count').textContent`
3. After any click attempt, re-check basket count — if unchanged, the click did not work
4. If all methods fail, fall back immediately — do not keep trying

Resolution priority:
1. Use the persistent browser via CDP with `Target.createTarget` and `Runtime.evaluate` for all navigation and interaction
2. If still failing: send the user the direct product link with price and description
3. Absolute fallback: `https://www.amazon.co.uk/gp/aws/cart/add.html?ASIN.1={ASIN}&Quantity.1=1`

### Fallback: Email Search

If unable to access Amazon order history directly:
1. Search email for messages from `auto-confirm@amazon.co.uk`
2. If Amazon starts using an alternative order confirmation address, update this list
3. Extract product details and prices from order confirmation emails

## Ordering Modes

### Mode 1: Reorder (exact)

When the user names a specific product they've bought before:
1. Look up the exact product in order history or email
2. Find the same product on Amazon
3. Send the user the link
4. Note if the price has changed

### Mode 2: Reorder-like (cheapest equivalent)

When the user says "order me some more X" or uses "reorder-like" language:
1. Identify the **brand** and **product type** from the previous order
   - Brand must match exactly
   - Product type must match (bubble bath, not soap or shampoo)
   - Size/variant/flavour can vary
2. Search Amazon for the product
3. Compare all available variants on the result page
4. **Select the best-value variant automatically:** unit-price comparison as per Mode 4 rules. The skill picks the cheapest variant, not the same one as before.
5. **Add directly to basket**
6. Report: "Added X to basket — £Y (was £Z last time). This is the cheapest variant available."
7. If in doubt about brand or product type, send 2-3 options for the user to choose from first — but default to just doing it.

### Mode 3: Fuzzy search (specific item, partial info)

When the user names a product but doesn't know the full name or brand:
1. Search Amazon for the keywords given
2. Identify the most likely match based on description and reviews
3. If multiple candidates, send the top options with prices
4. Confirm which one is correct before proceeding

### Mode 4: Best Value (unit pricing)

When the user asks which size/pack of a product is the best value:
1. Navigate to the product page on Amazon
2. Amazon shows size/pack variants with per-unit pricing (e.g. "£0.32/100 Sheets") — use these directly when available
3. If not shown, extract from product details:
   - Total unit count (e.g. "48 Count") and sheet count (e.g. "9600 sheets")
   - Calculate: price ÷ units = unit price
4. Build a comparison table of all variants
5. Always explain the unit measure (e.g. "pence per sheet", "pence per ml", "price per item")
6. **Bulk is NOT always best** — always calculate and show, don't assume
7. **Check different sellers** — the same product/size may have different prices from different sellers. Note if a lower price exists from a non-Prime seller.
8. Present the best value with a clear recommendation
9. **Subscribe and Save:** If S&S pricing is available, always check and report the S&S price alongside the one-time price. Present it as information — do NOT subscribe. Assume the user wants one-time purchase.

**Common unit measures by product type:**
- Toilet rolls → pence per sheet (or £ per 100 sheets)
- Nappies → pence per nappy
- Washing liquid/tablets → price per wash/load
- Food/drink → price per kg, per litre, or per 100g
- Cleaning products → price per use or per litre
- Toiletries → price per ml or per 100ml

### Mode 5: Research (curated product research)

When the user asks for product recommendations:
1. **Decide research scope:**
   - **Amazon-only** — when the product category is well-covered by Amazon (commodity items like kitchen tools, electronics accessories, basic household goods). Search Amazon, evaluate results, present findings.
   - **Prior research required** — when the question needs broader context first (gift ideas, specialist equipment). Search the internet for expert reviews, gift guides, recommendations, THEN cross-reference top picks on Amazon.

2. **Evaluation criteria:**
   - Brand reputation and heritage
   - Star rating AND number of reviews (a 4.7 star with 5,000 reviews beats a 4.9 star with 12)
   - Price relative to alternatives
   - Quality indicators in reviews (durability, actual performance vs marketing)
   - Prime eligibility

3. **Generic copies:**
   - Assess whether the generic is genuinely good value or a corner-cutting imitation
   - If generic is legitimately good: recommend both genuine and generic, labelled clearly
   - If generic is clearly inferior: mention it exists but don't recommend it
   - Default assumption: generics are fine for simple items (strainers, cables), risky for complex items (children's equipment, anything safety-related)

4. **Present a ranked list of ~5** with reasoning:
   - Rank by value-for-money, not just price
   - Explain WHY each ranks where it does
   - Note if a product is "genuine premium" vs "best budget" vs "best all-rounder"
   - Flag if something seems overpriced relative to alternatives

5. **Availability check:**
   - For prior research tasks: after finding top picks from internet research, check which are available on Amazon
   - If the best option isn't on Amazon, mention it — but don't search other retailers unless asked

### Mode 6: Add to basket

The natural-language to basket flow is:

1. **Parse the user's request:** extract brand (if any), product category, and any preferences (scent, size, quantity)
2. **Search Amazon** for the product using the brand name and keywords
3. **Evaluate results:** check brand match, reviews, Prime eligibility
   - For commodities: pick the cheapest Prime-eligible option
   - For branded items: pick the cheapest variant of the correct brand
4. **Compare variants** on the chosen product page: size, scent, pack-count, unit price
   - Use Mode 4 unit-pricing logic to select best value
   - If scent preference is stated, match it if available; otherwise pick cheapest scent
5. **Add to basket** using the Playwright CLI script (if available) or CDP:
   - `node amazon-basket-cli.js <parent_ASIN> --variant "<label>"`
   - The `--variant` flag is internal to the skill. The user never sees it. The skill computes the label from the variant comparison.
6. **Report:**
   - If successful: "Added X (variant) to basket — £Y. Ready for checkout."
   - If not logged in: "Can't add to basket — not logged in. Here's the link: <bare URL>"
   - If out of stock: "The cheapest option is out of stock. Next best is Z at £W. Want me to add that instead?"

### When NOT to ask for clarification
- **£20 and under commodities:** just do it (toilet paper, soap, food staples, toiletries)
- **Known brands where cheapest is obvious:** just do it
- **Identical product with different sizes:** auto-pick best value

### When to ask for clarification
- **£50+ or unfamiliar brands:** present top 2-3 options
- **Multiple distinct products** (e.g. "Apple charger" could mean 20W or MagSafe)
- **Gift or personal preference items:** present options
- **Multiple viable variants with unclear best value:** present comparison

## Unavailable / Discontinued Items

If the product is unavailable or appears discontinued on Amazon:
1. **Ask the user** before searching for alternatives:
   - "This item appears to be unavailable. Would you like me to search for an alternative, or leave it for now?"
2. If yes: find the closest match and present options
3. If no: stop

## Price Tracking

- When reordering, always compare current price to what the user previously paid
- Report: "Same as before", "Up from £X to £Y", or "Down from £X to £Y"

## Link Formatting (critical — cross-platform)

**Always send product links as bare URLs.** Never use markdown link syntax like `[text](url)` — that renders as dead text on some messaging platforms.

Correct: `https://www.amazon.co.uk/dp/B00GZOOLG4`
Wrong: `[Click here](https://www.amazon.co.uk/dp/B00GZOOLG4)`

This applies to all links in all responses: product links, research sources, external retailers.

## Mode 7: Returns

When the user asks to return an Amazon purchase:

### Automation boundary

1. **Find the order** — search order history for the product name
2. **Open the return flow** — navigate to the "Return items" link
3. **Select only the target item** — deselect any other returnable items in the same order
4. **Choose the reason** — from the AUI dropdown; always prefer the most honest/accurate reason
5. **Fill the comments field** — required for most reasons; be brief and factual
6. **Choose refund method** — stick with Amazon account balance (default)
7. **Check the acknowledgement checkbox**
8. **Choose carrier** — prefer Post Office > Evri. If neither available, surface to user.
9. **Select drop-off location** — for Post Office: enter postcode, pick nearest
10. **Stop before confirming** — always give the user the browser URL to review before clicking "Confirm your return"

### Step-by-step details

**Step 1: Find the order**
1. Navigate to `https://www.amazon.co.uk/gp/css/order-history`
2. Locate the order-specific search: `#searchOrdersInput` — NOT the main `#twotabsearchtextbox`
3. Set value via:
   ```js
   const input = document.querySelector('#searchOrdersInput');
   const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
   setter.call(input, 'product keyword');
   input.dispatchEvent(new Event('input', { bubbles: true }));
   ```
4. Submit: `input.closest('form').submit()`
5. Verify results show the correct item

**Step 2: Get the return URL**
1. Click "View order details" → URL contains `order-details?orderID=XXX-XXXXXXX-XXXXXXX`
2. Construct return URL: `https://www.amazon.co.uk/spr/returns/cart?orderId={orderID}`

**Step 3: Navigate returns page and select items**
1. Navigate to the return cart URL
2. **Checkboxes:** IDs match pattern `{itemKey}-{hash}-self_serviceable-orc-item-selection-checkbox`. The page shows ALL returnable items — ensure only the target is checked.
3. Set reason:
   ```js
   select.value = 'RO_CR-NOT_COMPATIBLE'; // or appropriate value
   select.dispatchEvent(new Event('change', { bubbles: true }));
   ```

**Step 4: Fill required comment**
After selecting reason, a conditional textarea appears. Set value using `Object.getOwnPropertyDescriptor` setter + `input`/`change` events.

**Step 5: Click Continue**
The Continue button is a `<span>`: `orc-items-section-continue-button-announce`. May need `dispatchEvent(new MouseEvent('click', {bubbles: true}))`. Watch for cookie consent traps.

**Step 6: Refund method**
- Stick with default (Amazon account balance — first radio, checked)
- **Acknowledgement checkbox** must be checked: ID pattern `{itemKey}-{hash}-{resolutionHash}-acknowledgementId`
- Continue: `#resolutions-section-continue-button-announce` (span)

**Step 7: Return method**
- **Default preference: Post Office** > Evri > surface to user
- Post Office: select radio → "Choose drop-off location" modal → postcode → nearest branch

**Step 8: Final confirmation boundary**
Present summary table and ask "Proceed with confirmation?" Only click when explicitly permitted.

### Defaults
- Reason: user provides (usually "Incompatible or not useful for intended purpose")
- Refund: Amazon account balance
- Carrier: Post Office > Evri
- Postcode: user provides

### Common reason values

| Reason | Value |
|--------|-------|
| Incompatible / not useful | `RO_CR-NOT_COMPATIBLE` |
| No longer needed | `RO_CR-UNWANTED_ITEM` |
| Defective / doesn't work | `RO_CR-DEFECTIVE` |
| Accidental order | `RO_CR-ORDERED_WRONG_ITEM` |
| Performance/quality inadequate | `RO_CR-QUALITY_UNACCEPTABLE` |
| Wrong item sent | `RO_CR-SWITCHEROO` |
| Damaged (box undamaged) | `RO_CR-DAMAGED_BY_FC` |
| Damaged by carrier | `RO_CR-DAMAGED_BY_CARRIER` |

### Key selectors

| Step | Selector pattern |
|------|-----------------|
| Order search | `/your-orders/search?opt=ab&search=<term>` |
| Return items link | `a[href*="/spr/returns/cart"]` |
| Item checkboxes | `[id$="-self_serviceable-orc-item-selection-checkbox"]` |
| Reason dropdown (native) | `[id$="-native-dropdown"]` first |
| Reason AUI popover | `xpath=../span[contains(@class,"a-button-dropdown")]` |
| Comments textarea | `textarea:visible` — appears after reason selected |
| Cart Continue | `[id$="items-section-continue-button-announce"]` (span, not input!) |
| Refund checkbox | `[id$="-acknowledgementId"]` |
| Refund Continue | `#resolutions-section-continue-button-announce` |
| Carrier radios | `input[type="radio"]:visible` — filter by carrier name via parent text walk |
| **"2 OTHER RETURN OPTIONS" expand** | `a:has-text("OTHER RETURN OPTIONS")` or `force=True` click |
| Drop-off chooser button | `[id$="-widget-trigger"]` |
| Postcode input | `input[type="text"]:visible` — filter OUT `name="field-keywords"` |
| Dropoff here button | `button:has-text("Dropoff here")` first |
| Confirm return | `button:has-text("Confirm your return")` |

### Carrier option discovery by text

When carrier options are collapsed, iterate radios and walk parent containers:
```js
const radios = document.querySelectorAll('input[type="radio"]');
for (const r of radios) {
  const container = r.closest('div, span, li');
  if (container) {
    const txt = container.innerText.toLowerCase();
    if (txt.includes('evri')) return {id: r.id, carrier: 'Evri'};
    if (txt.includes('asda')) return {id: r.id, carrier: 'ASDA'};
    if (txt.includes('post office')) return {id: r.id, carrier: 'Post Office'};
    if (txt.includes('royal mail')) return {id: r.id, carrier: 'Royal Mail'};
  }
}
```

### Pitfalls

1. **The "Continue" buttons are SPANs, not INPUTs.**
2. **The comments textarea is conditionally rendered.** Only appears AFTER reason dropdown triggers validation.
3. **The refund acknowledgement checkbox is separate from the radio.** Both must be handled.
4. **The "Choose drop-off location" flow opens a modal.** Postcode → search → "Dropoff here" — three steps.
5. **Cookie consent popover** can intercept clicks. Dismiss first.
6. **Multiple returnable items** — verify only the right item is checked.
7. Don't use `#twotabsearchtextbox` on order pages — it searches the catalogue, not orders.
8. Form `.submit()` beats button `.click()` for search submission.
9. Always use `Object.getOwnPropertyDescriptor` for setting values on React-controlled inputs.
10. **URL doesn't change between steps.** Read `document.body.innerText` for content changes.
11. **The hidden `<input type="submit">` behind the AUI Continue button does NOT work from CDP.** Use `dispatchEvent(new MouseEvent('click', {bubbles: true}))` on the visible span, or use a Playwright script which generates real pointer events.
12. **Native `HTMLFormElement.prototype.submit()` from CDP triggers Amazon bot detection.** The only reliable path for form submission past the items/reason step is real user interaction or Playwright with genuine pointer events.
13. **Even Playwright can struggle on the final Confirm button.** The final "Confirm your return" button is the boundary: stop and ask the user to click it manually.
14. **The returns script needs `AMAZON_RETURNS_HEADLESS=1` to run without X11.** If invoking Playwright without a display server, set this env var to avoid headed browser launch crashes.
15. **"2 OTHER RETURN OPTIONS" hides simpler carriers.** Evri Drop Off, Royal Mail Drop Off, and ASDA options are NOT visible by default — they live collapsed under this link. Use a precise selector, not text search (invisible placeholder divs also contain the text).
16. **Post Office modal "click here" trap opens royalmail.com.** A link labelled "click here" inside the drop-off modal is NOT a branch selection — it opens royalmail.com and kills the return flow. Never click it.
17. **Post Office carrier radio may need `page.mouse.click()` instead of `.check()`.** `radio.check()` may not visually select it. `page.mouse.click()` at the radio's bounding box center works.

### Returns script

If a Playwright script is available at `scripts/amazon-returns-cli.js`, it connects to the persistent browser via CDP and walks through the return flow:

```bash
node scripts/amazon-returns-cli.js "product name" "incompatible or not useful" --auto-confirm
```
- `--auto-confirm` skips all human approval and clicks "CONFIRM YOUR RETURN"
- The script handles carrier fallback automatically: Evri → ASDA → Post Office/Royal Mail
- If no carrier succeeds, it prints a message and exits for manual completion

### Key implementation detail: clickAuiSubmit

Amazon's AUI "Continue" and "Confirm" buttons are `<span>` wrappers around a hidden `<input type="submit">`. Synthetic JS clicks are rejected by Amazon's anti-bot layer. The script clicks the **actual submit input** (found via `getBoundingClientRect` inside the AUI wrapper) using Playwright's real pointer dispatch. This is the only reliable method.

## Scripts

- `amazon-basket-cli.js` (root) — connects to persistent Chromium via CDP, uses native `.click()` for genuine pointer events. The only reliable add-to-cart method.
- `scripts/amazon-returns-cli.js` — connects to persistent Chromium via CDP, walks through return flow, handles carrier fallback.

## Notes

- Login: assume the user is already logged in (persistent browser session)
- If login is required, stop and ask the user to log in manually
- Always show prices in GBP (or local currency for other regions)
- Prefer Prime-eligible items when equivalent options exist
- Record useful product research to skill files if the user wants to save it