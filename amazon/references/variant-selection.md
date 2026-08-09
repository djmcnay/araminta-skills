# Amazon Variant Selection — Basket-Add with Playwright CLI

## Overview

The `amazon-basket-cli.js` script handles two scenarios:

1. **Direct add** (no variants): `node amazon/amazon-basket-cli.js <ASIN> [quantity]`
2. **Variant-select then add**: `node amazon/amazon-basket-cli.js <ASIN> --variant "24 Count"`

Fuzzy matching on visible twister button text (e.g. `"strawberry"`, `"pack of 2"`, `"raspberry 3"`). The script clicks the matched variant, waits for the buy box to re-render, then clicks Add to Basket.

## How variant extraction works

The script runs `page.evaluate()` inside persistent Chromium (CDP port :9222) to reach the real DOM that bot-mitigated browsers hide:

### Strategy 1 — ID-based twister buttons (preferred)

Query: `[id^="size_name_"], [id^="colour_name_"], [id^="flavour_name_"], [id^="scent_name_"], [id^="pack_name_"], [id^="style_name_"], [id^="count_name_"]`

Each button element:
- `innerText` contains: label, price, unit price, delivery info
- Skip `-announce` suffixed copies (they are accessibility duplicates)
- ID is stable per session: `size_name_4` = 24 Count (Pack of 1)

**Example extracted variant:**
```json
{"id":"size_name_4","label":"24 Count (Pack of 1)","price":"£17.00","unitPrice":"£0.35 /100 Sheets","element":"twister"}
```

### Strategy 2 — Fallback `.a-button-toggle` class

Only used if no twisters found. Scans all `.a-button-toggle` elements, filters out noise:
- Skip elements with text matching: `"Load more"`, `"Resume response"`, `"Create a free account"`, `"Try Today"`, pagination controls (`/^\d+\+$/`)

### Strategy 3 — Select dropdowns

Looks for `<select>` elements whose name/id/aria-label contains: `size`, `colour`, `flavour`, `scent`, `style`, `count`, `pack`.

## Fuzzy matching

The `matchVariant()` function uses a scoring system:

| Match type | Score |
|------------|-------|
| Exact string match (case-insensitive) | 1000 |
| Label starts with query | 500 |
| Query words are all present in label | 100 per word |
| Exact word match (query is a single word equal to a label word) | +50 bonus |

Threshold: score >= 100 to return a match.

**Behaviour:**
- `"raspberry"` matches `"Raspberry Scent (Pack of 2)"` (word present)
- `"24 Count"` matches `"24 Count (Pack of 1)"` (starts with)
- `"strawberry 3"` matches `"Strawberry (Pack of 3)"` (both words present)
- If no match, the script exits listing all available variants so the user can re-query.

## Buy-box re-render after variant click

**Critical:** After clicking a twister variant, Amazon's buy box (including price, availability, and the Add to Basket button) is replaced via AJAX. The old button remains in the DOM but hidden.

Problem: `page.locator("#add-to-cart-button").isVisible()` may return `true` on the OLD hidden element, or `false` because the new button hasn't rendered yet.

**Solution:** Poll multiple selectors over 5 attempts with 1-second delay:
```javascript
const addBtnSelectors = [
  '#add-to-cart-button',
  'input[name="submit.add-to-cart"]',
  '[name="submit.add-to-cart"]',
  'input#add-to-cart-button',
  '#desktop_qualifiedBuyBox #add-to-cart-button',
];
```

First selector that resolves to a visible element wins.

## What NOT to use for variant/basket operations

### ❌ Camoufox / browser_navigate
- Camoufox's anti-bot fingerprinting breaks Amazon's AJAX event pipeline
- Clicking a twister variant may visually change the page but the add-to-cart XHR never fires
- Basket count stays unchanged
- **Rule:** Camoufox is for browsing/reading only. Persistent Chromium is for basket ops.

### ❌ browser_cdp Runtime.evaluate + .click()
- Even with genuine pointer events from Playwright, running `.click()` via `browser_cdp(Runtime.evaluate)` on Chromium may still fail because Amazon's JS checks event origin
- The Playwright script uses `elementHandle.click()` (real pointer event) through the Playwright-CDP bridge, not raw CDP evaluate

### ❌ Accessibility tree browser_click
- The accessibility tree exposes `@e19` labelled "Add to basket, shift, ALT, K" — this is a keyboard shortcut list item, not the real buying widget button
- Clicking it fires the shortcut handler, not the add-to-cart AJAX
- The real `#add-to-cart-button` is NOT exposed in the accessibility tree

## Testing the script

```bash
cd ~/Documents/GitHub/araminta-toolshed/amazon
node amazon-basket-cli.js B07TS96K9G --variant "24 Count"
```

Expected output flow:
1. "Connecting to persistent Chromium..."
2. "Found 6 variant(s)" with list
3. "Matched variant: 24 Count (Pack of 1) @ £17.00"
4. "New price after variant selection: £17.00"
5. "Found add button via: #add-to-cart-button"
6. "Basket count after: 1"
7. JSON output with success, title, price, variant details

## Variant ASINs vs parent ASINs

Amazon product pages with variants load a **parent ASIN** (e.g. B07TS96K9G = Cheeky Panda). The 24 Count variant does NOT have a separate child ASIN that loads directly — the variant is only selectable via the twister on the parent page.

Conversely, some products have separate ASINs per variant. In that case the user can pass the child ASIN directly: `node amazon-basket-cli.js < CHILD_ASIN >`

When in doubt, use the parent ASIN + --variant flag.

## Session-specific findings

### Cheeky Panda (B07TS96K9G) — tested 20 May 2026
Twister buttons:
- `size_name_5` = 48 Count (Pack of 1) @ £34.00
- `size_name_0` = 4 Count (Pack of 1) @ £4.60
- `size_name_1` = 9 Count (Pack of 1) @ £6.95
- `size_name_4` = 24 Count (Pack of 1) @ £17.00 ← best value per-sheet
- `size_name_2` = 9 Count (Pack of 2) @ £13.90
- `size_name_3` = 9 Count (Pack of 5) @ £39.99

Unit-price comparison: 24-pack and 48-pack tied at £0.35/100 sheets.

### BrosTrend Dongle (B0F6N1H84N) — tested 18 May 2026
No variants. Direct add. Price: £19.99.

## Troubleshooting

### "Not logged in as the user"
The script evaluates `document.body.innerText` to check for "Hello, [name]" text anywhere on the page. If this fails:
1. Navigate to `https://www.amazon.co.uk` in persistent Chromium and verify the header
2. If not logged in, the user needs to log in manually in the browser
3. Restart the persistent Chromium service if cookies were cleared

### "Add to Basket button not found on page after waiting"
The buy box may be in an unusual state (sold out, delivery unavailable, or Amazon may have A/B tested a new layout).
- Check if the product shows "Currently unavailable" 
- Check if there's a "See all buying options" button instead
- If stuck, fall back to sending the direct product link

### "No variant matched"
The variant list is printed. Re-query with text that appears in the labels, or use `web_search` to check if the variant exists as a separate ASIN.
