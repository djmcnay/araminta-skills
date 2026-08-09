# Pi Zero 2W — Multi-Source Price Tracking

## Why this document exists
This captures the multi-source tracking pattern used for Raspberry Pi Zero 2 W stock and price monitoring. The UK is universally out of stock, so the goal is "alert when any official reseller has stock at ≤£20.

## Sources tracked

| ID | Source | URL | Type | Pattern | Notes |
|---|---|---|---|---|---|
| `rpi-zero-2w-thepihut` | The Pi Hut | https://thepihut.com/products/raspberry-pi-zero-2-w | Shopify | `stock_and_price` | Official UK reseller. Standard listing, no variant selectors. |
| `rpi-zero-2w-pimoroni` | Pimoroni | https://shop.pimoroni.com/products/raspberry-pi-zero-2-w?variant=39493046075475 | Shopify | `stock_and_price` | Variant: "with pre-soldered header". the user is indifferent to headers. |
| `rpi-zero-2w-amazon` | Amazon UK | https://www.amazon.co.uk/s?k=Raspberry+Pi+Zero+2+W | Amazon search | `price_threshold` | Search result: resellers often charge £25-40. Only alert at ≤£20. |

## Scraper strategy per platform

### Shopify (Pi Hut / Pimoroni)
Shopify product pages are large (100K+ characters) and can trigger web_extract's summarizer timeout or size limits. The summarizer may return "No featured offers available" even when the item is in stock.

**Recommended check order:**
1. `web_extract` first — may return a summary with structured pricing despite the noise. Look for `product.title`, `price`, and `availability` in the JSON-LD.
2. If empty: `web_search` with `site:thepihut.com "Raspberry Pi Zero 2 W" price stock`
3. If still empty: mark price as `null` and log the issue. Do NOT claim "unavailable" — the summarizer is unreliable on Shopify.

### Amazon (search results)
Amazon search results don't have a single ASIN for Pi Zero 2 W — resellers list at various prices. The price-spy cron should:
- Search the query: `"Raspberry Pi Zero 2 W" site:amazon.co.uk price`
- Extract the cheapest listing from search snippets
- Only log if a GBP price is found
- Log the seller name and Prime status in `observation`

## Re-appearance detection
When an item has been out of stock for multiple consecutive checks (price: null), the web_extract summarizer tends to cache stale "no featured offers" text. On Shopify:
- If the page loads and contains a structured `price` with a `validFrom` or `availability` URL, trust that over the plain text
- If all structured data is missing but the page loads fully (no 404), log a note about "suspected restock — page present but no price found" rather than claiming unavailability

## Alert threshold
- Target: ≤£20 (RRP range is £15-20)
- the user wants "a few" units — multiple alerts welcome
- No need to suppress repeat alerts for the same source once stock is back: if PiHut has stock for 3 days, alert on day 1 only (standard price-spy dedupe), but if Pimoroni ALSO comes in stock on day 2, that's a separate source and a separate alert

## Variant indifference
the user explicitly stated: "don't care if they have installed headers or not." When reporting, note the variant present but do not ask the user to choose. Default to the cheapest variant across sources.
