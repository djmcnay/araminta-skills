# Algolia Retail API Discovery

## When to use this
A retailer's product listing page is a Next.js/React SPA that loads catalog data client-side. Instead of fighting with browser automation or web_extract against a virtualized DOM, check whether the site exposes its Algolia search credentials in the initial HTML payload.

## Why it matters
- Bypasses lazy-loading / virtualized rendering (only 12 of 80+ products may exist in the DOM at once)
- No browser needed — curl + jq/python is enough
- Filters, facets, sorting, and pagination are all first-class API parameters
- Resilient against UI redesigns

## Discovery steps

### 1. Load the page and look for `__NEXT_DATA__`
```bash
curl -s 'https://www.retailer.com/en-gb/products' | grep -o '__NEXT_DATA__.*' | head -1
```

Or read the HTML source for a `<script type="application/json" id="__NEXT_DATA__">` block.

### 2. Extract Algolia config from the JSON payload
Look for keys like:
- `algolia_app_id`
- `algolia_search_api_key` (read-only key — safe to use)
- `algolia_index_name`

These are typically under `props.pageProps.config` or similar.

### 3. Test the index
```bash
curl -s -X POST "https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX_NAME}/query" \
  -H "X-Algolia-Application-Id: {APP_ID}" \
  -H "X-Algolia-API-Key: {SEARCH_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"","hitsPerPage":1}'
```

### 4. Find the right facet fields
The same `__NEXT_DATA__` payload lists filter definitions. Look for:
- `filterProps` — maps display names to facet attribute names
- Example: `{"value":"WEB_BAGSIZE_en_GB","displayName":"Bag Size"}`

Also inspect a sample hit to confirm field names. Some sites use locale-suffixed attributes (e.g. `_en_GB` vs `_en_US`).

### 5. Build the filtered query
```bash
curl -s -X POST "https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX_NAME}/query" \
  -H "X-Algolia-Application-Id: {APP_ID}" \
  -H "X-Algolia-API-Key: {SEARCH_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "facetFilters": [
      ["FACET_FIELD:value1"],
      ["FACET_FIELD2:value2"]
    ],
    "hitsPerPage": 100,
    "attributesToRetrieve": ["productName","brand","price","unit_pricing","PDP_URL"]
  }'
```

## Worked example: beanz.com (UK)

**Page:** `https://www.beanz.com/en-gb/coffee`

**Algolia credentials (from `__NEXT_DATA__`):**
- App ID: `VBT275CJRZ`
- Search API Key: `93a2a727bf6bfa039a385e9c922e3daf`
- Base index: `Beanz`

**UK-specific index name:** `Beanz_UK` (discovered by testing `Beanz_en_GB`, `Beanz_GB`, `Beanz_UK`)

**Facet fields (from `filterProps` in payload):**
- Bag Size → `WEB_BAGSIZE_en_GB`
- Brew Method → `Brew_method`
- Caffeine → `Looking_for_Decaf`

**Sample query for 1kg Espresso Caffeinated:**
```bash
curl -s -X POST 'https://VBT275CJRZ-dsn.algolia.net/1/indexes/Beanz_UK/query' \
  -H 'X-Algolia-Application-Id: VBT275CJRZ' \
  -H 'X-Algolia-API-Key: 93a2a727bf6bfa039a385e9c922e3daf' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "",
    "facetFilters": [
      ["WEB_BAGSIZE_en_GB:1 kg"],
      ["Brew_method:Espresso"],
      ["Looking_for_Decaf:No"]
    ],
    "hitsPerPage": 100,
    "attributesToRetrieve": ["productName","Our_Roasters","displayPrice","unit_pricing","The_Roast","Coffee_Flavors","PDP_URL"]
  }'
```

**Result:** 81 coffees, £25.00–£56.95 per kg. Sorted by price server-side or client-side.

## Pitfalls

### "Browser is the default" — wrong instinct
When the user asks about a retail site with a product grid (e.g. beanz.com), the agent instinct is often to open `browser_navigate` and scroll. **DO NOT do this for Algolia-backed Next.js sites.** Browser tools see only the first ~12 products rendered on initial load, Algolia filters are client-side state machines that may not reflect actual facet counts, and lazy-loading makes scrolling through 100+ products impractical. Always check for `__NEXT_DATA__` FIRST. If Algolia credentials are present, use them. If not, fall back to browser tools. See `research` skill for the multi-agent pipeline — this applies there too.

### Locale-suffixed vs base facet names
The browser UI may show `Brew_method` in filters, but the actual indexed attribute could be `WEB_Brew_method_en_GB`. Inspect sample hits to confirm. Try the base name first; fall back to the locale-suffixed version if `facetFilters` returns zero hits.

### US vs UK index divergence
The base index name (`Beanz`) may be US-only. Test locale-specific variants (`_UK`, `_en_GB`, `_GB`) if the base index returns wrong-currency hits or the wrong product count. The UK site showed 127 total products in `Beanz_UK` vs a different catalog in the US index.

### `facetFilters` syntax
Each inner array is an AND condition. Outer arrays are OR across their inner elements.
```json
["field:A", "field:B"]     // field=A AND field=B
[["field:A"], ["field:B"]] // field=A OR field=B
```

### Read-only keys only
The embedded key is always a search-only key. It cannot write, delete, or admin the index. Safe to use — no credential leakage risk beyond reading public catalog data.

## When NOT to use this
- Sites that do not use Algolia (obviously) — fall back to browser extraction or web_extract
- Sites where the Algolia index is behind additional server-side auth (rare for public PLPs)
- When the user explicitly wants visual confirmation (screenshots, UI verification)

## Related skills
- `price-spy` — for ongoing price monitoring once the API is known
- `browser-extraction` — fallback when no embedded API is available
- Scripts: `scripts/algolia-retail-query.py` — reusable Python script for querying any discovered Algolia API (pass a URL, get JSON back)
