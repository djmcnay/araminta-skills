# Shopify Collection-Page Fallback for Price Verification

## When to use
When a Shopify product page (e.g. `campbellsofbeauly.com/products/...`) fails `web_extract` due to page size (common — Shopify sites bundle enormous JS/CSS that gets truncated at the 5,000-char limit) or times out.

## Target retailers

### Campbell's of Beauly
- **Product page pattern:** `https://www.campbellsofbeauly.com/products/men-winter-aigas-field-jacket`
- **Collection page pattern:** `https://www.campbellsofbeauly.com/collections/auld-stock`
- **Search query that works:** `site:campbellsofbeauly.com "Auld Stock Winter Aigas Field Jacket" price £`
- **Verified:** The Auld Stock collection page renders product titles + sale prices in search snippets. The product page itself is ~13,000 chars of HTML and times out `web_extract` summarisation.

## Method
1. Search `site:<retailer.com> "<exact product name>" price £` — Google/DDG snippets show the price directly from structured data
2. If that fails, search the retailer's collection or category URL: e.g. `site:campbellsofbeauly.com "Auld Stock" "Sale Price"` — the collection page listing shows prices more compactly
3. Cross-reference the search result URL to confirm it's the same product, not a different variant
