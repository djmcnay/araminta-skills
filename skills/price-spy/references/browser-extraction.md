# Browser extraction notes for price-spy

Session-proven patterns:

## Amazon product pages
- Use `browser_navigate` to the ASIN URL, then read the live DOM with `browser_console`.
- **Price extraction — preferred selector chain (try in order):**
  1. `document.querySelectorAll('.a-price .a-offscreen')[0]?.textContent` — returns the canonical visible price text (e.g., `"£44.00"`). Works reliably when the price DOM has loaded.
  2. `document.querySelector('#corePrice_desktop .a-price .a-offscreen')?.textContent` — older selector for the "strike price" area; Amazon has moved price elements outside `#corePrice_desktop` so this often returns null now. Not recommended as primary selector.
  3. `document.querySelector('.a-price-whole')?.textContent` — reliably returns the integer portion (e.g. `"34."` or `"49."`) even when `.a-offscreen` is empty. **Pitfall:** the innerText includes a trailing period (e.g. `"49."`), so strip it with `.replace('.','').trim()` before parsing.
  4. `document.querySelector('.a-price-fraction')?.textContent` — returns the fractional portion (e.g. `36` for £49.36). Combine with `.a-price-whole` to get the full price.
- **Complete price extraction pattern (canonical):**
  ```
  const offscreen = document.querySelectorAll('.a-price .a-offscreen')[0]?.textContent;
  const whole = document.querySelector('.a-price-whole')?.textContent?.replace('.','').trim();
  const frac = document.querySelector('.a-price-fraction')?.textContent?.trim();
  const priceText = offscreen || (whole ? (frac ? whole + '.' + frac : whole) : null);
  const price = priceText ? parseFloat(priceText.replace(/[^0-9.]/g, '')) : null;
  ```
- Stock selector that worked reliably: `document.querySelector('#availability span')?.textContent?.trim()`
- For variant items, navigate directly to the variant ASIN when the parent listing is ambiguous.
- `browser_snapshot` is useful for confirming the page title and that the right product loaded before extracting values.
- **Pitfall — DOM leak between navigations:** When checking multiple items in sequence, `browser_console` can return prices from the *previous* page if the navigation hasn't completed. Always verify the page title matches the expected product before trusting the extracted values. A simple check: `document.title` should contain the product name or ASIN.

## Shopify / Campbell's of Beauly
- Cookie consent can block extraction. Accept the consent dialog first, then re-run extraction.
- The product page usually exposes sale price and regular price directly in the DOM once consent is handled.
- Look for stock text such as "Only 2 Available" in the page body rather than relying on product-card summaries.
- **Accessibility tree pattern (most reliable):** When `browser_navigate` loads a Campbell's product page, the accessibility snapshot consistently exposes three labelled elements in the DOM: `"Sale Price"` with a companion `"£495.00"` element, `"Regular Price"` with `"£825.00"`, and a `"Only 2 Available"` paragraph. These appear as labelled StaticText elements in the snapshot — not buried in `<script>` tags or truncated content. This is the canonical extraction method for Shopify's Dawn/structured theme.
- If `browser_navigate` succeeds, do not use `web_extract` for the same Shopify page — `web_extract` truncates at ~5,000 chars of HTML (Shopify pages are 12,000+ chars) and the summariser often misses the price entirely. The accessibility snapshot from `browser_navigate` is both more complete and more reliable.

## Reporting notes
- If all items are stable and no alert condition fired, a table of the full active watchlist is the right fallback report for a run.
- When running and reporting with an explicit instruction to produce output, always show the full watchlist table if nothing is notable. The user asked for information; provide it.
- Use per-variant comparison (item vs its own previous entry, not last-history-entry vs second-last) to avoid false deltas from interleaved variant checks.
