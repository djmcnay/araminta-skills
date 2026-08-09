# Amazon UK Unavailability Patterns

When scraping Amazon UK, products can appear unavailable in several distinct ways. Distinguishing between them is critical for correct alerting.

## 1. "No featured offers available" (Listing exists, no buy box)

**Detection:** web_extract returns content but the price section says "No featured offers available at time of listing" or "We feature offers with an Add to Basket button when an offer meets our high quality standards for..."

**Typical causes:**
- Item cannot be dispatched to the selected delivery location (e.g., UK-only shipping issue)
- Sold by third-party sellers only, not Amazon directly, and none currently have active offers
- Regional restriction — the listing exists but can't ship to the default region
- ASIN may have been migrated to a new listing

**Price_history note format:**
```
UNAVAILABLE on Amazon UK. 'No featured offers available — item cannot be dispatched to selected delivery location.'
```

## 2. "Currently unavailable" (Stock exhausted)

**Detection:** web_extract returns the product page but explicitly says "Currently unavailable" in the buy box area. The URL resolves normally. Product details, reviews, and images all load.

**Typical causes:**
- Temporarily out of stock (will likely restock)
- Discontinued (check if product is marked "Is Discontinued by Manufacturer: No" in specs)
- Seasonal item between seasons

**Price_history note format:**
```
UNAVAILABLE on Amazon UK. 'Currently unavailable' — no featured offers. Previously in stock at £XX.XX on [date].
```

## 3. URL returns 404 / empty page (Genuine delisting)

**Detection:** web_extract returns no content, an error message, or a dead listing result. Product cannot be found.

**Typical causes:**
- Product truly discontinued
- ASIN changed — product migrated to a new listing (common when brands restructure)
- Seller pulled the product from Amazon
- Product replaced by new model

**Action:** Initiate full Product Disappearance flow — search for replacement URL/ASIN.

## 4. Global Store pricing shift

**Detection:** web_extract from amazon.co.uk shows USD pricing (e.g., "$66.06") rather than GBP. The seller is "Amazon US" or "Amazon Global Store UK." The product is now imported from the US.

**Typical causes:**
- Amazon UK no longer stocks the item directly
- Item moved to Global Store program only
- Currency mismatch — the listing still works but prices in USD

**Price_history note format:**
```
White variant now appears to be sold via Amazon Global Store (US import, $66.06 USD). UK buy box price unclear — may have shifted to import-only pricing structure.
```

## 5. Partial variant availability

**Detection:** One variant (colour/size) of a product shows "No featured offers" while another variant remains in stock and priced normally.

**Typical cause:**
- Amazon UK sold out of specific colours/sizes
- Different ASINs have different stock levels
- Some variants maintained by different sellers

**Action:** Report each variant's status independently in price_history. Do not assume the entire product line is unavailable.

## 6. The "was unavailable, now back" pattern (re-appearance)

**Detection:** A product that showed "No featured offers" on a previous check now has a price and buy box again. The canonical test uses browser DOM extraction — trust `document.querySelector('#corePrice_feature_div .a-price .a-offscreen')` over the web_extract summariser text when they conflict.

**Typical causes:**
- Restocked by Amazon or a seller
- New seller stepped into the buy box
- Temporary listing issue resolved (e.g., regional carrier problem)
- Seasonal / batch restock (common for Fellow products)

**Multi-variant re-appearance (critical to detect):**
- If ALL variants of a product return on the same day after being unavailable, this signals a **supply-side event** (warehouse restock, new seller batch, or Amazon UK re-opened purchasing). This is more significant than a single variant trickling back.
- Log the full picture: which variants returned, at what prices, and how long they were gone.
- Re-appearance of all variants simultaneously may indicate a limited window before stock runs out again.

**Price_history note format:**
```
BACK IN STOCK on Amazon UK at £XX.XX. In stock. Previously unavailable for N consecutive days (May 4-9). Price back to pre-unavailability level.
```

## 7. USD-to-GBP pricing flip-back

**Detection:** An item that had been showing USD pricing (via Amazon Global Store) for multiple checks suddenly shows a GBP price and standard UK buy box again. The currency context on the page changes from `$XX.XX` to `£XX.XX`.

**Typical causes:**
- A UK seller restocked, reclaiming the buy box from the Global Store listing
- Amazon UK's own stock returned, displacing the US import offer
- Temporary routing issue (e.g., page was loading a US-centric variant of the listing)

**Action:** Log the GBP price restoration clearly — this is a meaningful change even if the price itself hasn't dropped much. The item is back on normal UK Prime terms. Note the previous USD price for context.

**Price_history note format:**
```
Price back to GBP £XX.XX (was showing in USD at $XX.XX on [date]).
```

## 8. Simultaneous multi-variant unavailability (product-line outage)

**Detection:** All variants of a product (all colours, all sizes) show "No featured offers" on the same day. Previously at least some variants were available.

**Typical causes:**
- Amazon UK delisted the entire product line temporarily (common before restock)
- Brand/Amazon contract renegotiation
- Listing migration to new ASINs
- Genuine sell-out across all sellers

**Action:** Check whether the individual variant ASINs still resolve. If all ASINs show the same "No featured offers", this is likely a buy-box issue affecting the whole product family. If some ASINs 404, it's a genuine delisting. Log the distinction.

**Price_history note format (after multiple days):**
```
STILL UNAVAILABLE on Amazon UK. All N variants remain unavailable. Page loads but buy box empty. Nth consecutive day.
```
