# Extraction Edge Cases & Techniques

Collected from operational runs against real Amazon UK and non-Amazon retail pages. Add to this file as new edge cases emerge.

## Idealo as a cross-reference for pricing

When web_extract on Amazon returns product content but no explicit GBP price (e.g., the extraction shows specs and reviews but misses the buy-box price), use idealo as a structured-data fallback.

**Pattern:** `https://www.idealo.co.uk/compare/{product-id}/{product-slug}.html`

**What you get:**
- Exact per-merchant pricing in a table, including Amazon UK
- Delivery costs broken out separately
- Total price (item + delivery) calculation
- Shop ratings and stock indicators
- Product metadata (volume, ABV, region for whisky)

**When to use:**
- Amazon page extraction gives content but no price in GBP
- You need to validate an Amazon price against competitors
- A whisky, spirit, or commodity product that idealo lists (they have extensive whisky/coffee/kitchen catalogues)

**Example (Arran 10 Year, May 6):**
- idealo showed amazon.co.uk at £44.00 with free delivery — lowest total price
- masterofmalt at £41.98 + £4.95 = £46.93 — cheaper base but more expensive delivered
- This let us report the actual competitive position, not just the Amazon price

## Cached vs live price discrepancy

**Pitfall:** Google search snippets for Amazon URLs can show a cached price that differs from the live price. This is especially common for "Currently unavailable" or "No featured offers" items.

**Concrete case (May 6, Fellow Atmos):**
- Google snippet from search: `£40.00`
- Live page: `No featured offers available`
- The £40.00 was the last known price, not current

**Rule:** Never use a search-snippet price as the sole data point. If the extracted page says "No featured offers" or "Currently unavailable", that takes priority over anything in a search snippet. Log the snippet price in `observation` for context, but record `price: null` in history.

## Alternate URL format for web_extract

When `web_extract` with `/dp/ASIN` format returns an error or empty content, try the full product-path format:

```
# Short form (may fail)
https://www.amazon.co.uk/dp/B0FH2THHBK

# Full product path (often succeeds when short form doesn't)
https://www.amazon.co.uk/Normcore-53-3mm-Spring-Loaded-Self-Leveling-Portafilters/dp/B0FH2THHBK
```

**When to use:** After first web_extract on `/dp/ASIN` gives an error or empty result, try the long form before falling back to web_search. Search for the product title + ASIN to discover the full path URL.

## Consecutive-day stale unavailability suppression

After an item has been "unavailable" for 3+ consecutive days with no change, the stale-unavailable status itself is no longer newsworthy. Still record it in `price_history` for continuity, but the report should not treat "still unavailable" day 3 as notable unless:
- A previously unavailable variant becomes available
- The listing changes (different message, new seller appearance)
- The item genuinely disappears (404 vs "No featured offers")

**Rule of thumb** for report criteria:
- Day 1 unavailable → notable (new disappearance)
- Day 2 still unavailable → notable (confirmed not a fluke)
- Day 3+ still unavailable → not notable unless accompanied by other change

## USD pricing on amazon.co.uk (Global Store shift)

When web_extract on an amazon.co.uk URL returns prices in USD (e.g., `$5.66` or `$66.06`), the item has moved to Amazon Global Store / sold by Amazon US. Indicators:
- Price shown with `$` not `£` prefix
- Delivery quoted in USD
- Seller listed as "Amazon US" or Global Store

**What to record:**
- Log the USD price in `observation` with clear notation that it's USD on a .co.uk page
- Record `price: null` if there's no GBP buy-box price (the skill tracks GBP prices)
- Note the direct-from-brand alternative if known (e.g., Childs Farm at £5.00 vs Amazon Global Store at USD 5.66)

## Multi-retailer price context

When tracking an item on Amazon, it's useful to check 1-2 competitor prices for context so the report can say "still above target but cheaper elsewhere" or "Amazon is actually the best deal despite being above target."

**Good sources per category:**
- Whisky: idealo.co.uk, masterofmalt.com, thewhiskyexchange.com
- Coffee gear: idealo.co.uk, Borough Kitchen (for Fellow products)
- General: brand's own website — often direct-price is competitive
