---
name: price-spy
description: Price watchlist — track products across retailers, alert when prices drop below targets or items become available in specific conditions.
ownership: collab
category: productivity
---

# Price-Spy — Price Watchlist Skill

## What It Does
Track products across retailers. Monitors prices, stock levels, and condition availability. Designed to scale to 100+ items — only surfaces what's important.

**Not a buying skill.** Pure monitoring and alerting. For Amazon items, can suggest adding to basket after an alert.

## Architecture

```
items.json (single source of truth)
  ↑
  │  run (scrape & update)     ← cron, batch, or on-demand
  │
  │  report (read & interpret) ← admin brief, on-demand, or triggered
  │
  ↓  output to the user
```

## Three Operations

### 1. Run — scrape and update (silent)
Scrape all items, update `items.json` with latest prices and observations. **No output. No report.** Just updates the data.

Used by:
- Daily cron job
- Batch updates alongside other data trackers
- On-demand when the user says "run price-spy"

**Flow:**
1. Read `items.json`
2. For each active item:
   a. If `price_source` is set → call that skill's price-check function
   b. **Algolia-first check (Next.js / SPA retail sites):** Before resorting to browser tools on any site with a filterable product grid (e.g. beanz.com), attempt to discover an embedded Algolia API via `__NEXT_DATA__`. If found, query it natively — this gives the full catalog, facets, sorting, and per-kg pricing without fighting lazy-loaded virtual DOMs or client-side filter state. See `references/algolia-retail-api-discovery.md`.
   c. If `price_source` is null → best-efforts anti-detection browser scrape of `url`
   d. For variant items: check each variant individually
   e. For condition tracking (`used_very_good`): check "Other Sellers" / "Buy Used"
3. Log result to `price_history` — price, condition, and contextual `observation`
4. If product URL is dead → search for replacement (see Product Disappearance)
5. **No output to the user.** Data is in `items.json` for later reporting.

**Exception:** If an alert condition is met during a run (price crossed threshold, used condition appeared), send an alert immediately. Don't wait for a report.

**Alert delivery channels (in priority order):**
1. **Telegram** (primary) — send via `send_message` tool to explicit numeric chat ID (e.g., `telegram:<your-chat-id>`). Never use display names like "the user (dm)" — the delivery layer cannot resolve them.
2. **WhatsApp** (fallback) — only if the WhatsApp bridge is running and reachable at `<whatsapp-bridge-url>`. Test with a lightweight message first; if connection refused, fall back to Telegram.
3. **Discord** (not used for alerts) — the user's Discord is a backup surface for scheduled reports only, not for real-time alerts.

**Alert format (Telegram):**
```
🔔 Price Spy alert

[Item name]
Now: £XX.XX ([condition])
Target: £XX.XX
[URL]

Want me to add to basket? (Amazon only)
```

### 2. Report — interpret and surface (read-only)
Read `items.json`, compare recent entries, surface only what's interesting. **Does not re-scrape.**

Used by:
- Admin brief (appends a price-spy section)
- On-demand when the user says "price spy report" or "what's the price spy saying"
- After a run when the user says "run price-spy and report back"

**What's interesting (report these):**
- Price crossed a threshold (went below target)
- Price moved significantly since last check (£2+ or 5%+ change)
- Item became unavailable on the retailer, or previously unavailable items came back
- Stock dropped to last few (≤3 remaining)
- Item appeared or disappeared
- Used condition became available (when tracking used)
- Product URL changed (listing moved)

**What's NOT interesting (skip these):**
- Stable prices (even if checked 100 times)
- Plenty of stock ("in stock", "15+ available")
- No change from last check
- Items sitting above their target with no movement

**Report format (for admin brief or on-demand):**
```
🔍 Price Spy

• Fellow Atmos — ALL THREE VARIANTS UNAVAILABLE on Amazon UK (was £35-£40 on May 2)
• Normcore Tamper — £47.01 (Black), under £50 target

(5 items watched, 2 notable, 3 unchanged)
```

If nothing is interesting: `🔍 Price Spy — no changes worth noting`

**Fallback reporting when scraping fails:**
If browser tools are partially failing but you managed to get some data (via web_extract, search snippets, or prior history), still report. Include a note like "(limited data — browser was unreliable)" in the report header. Do not suppress the report entirely just because some items couldn't be re-checked — the items that DID get checked still matter.

**Report-delivery for cron runs:**
When running as a cron job, your final response IS the report. Format it as a deliverable. 

**Silent vs visible behavior — critical distinction:**

- **Default cron (user gave no instruction, or simply said "run price-spy"):** If nothing is notable, respond with exactly `[SILENT]` (no other text) to suppress delivery. This avoids flooding the user's inbox with "nothing changed" messages day after day.
- **Explicit instruction to report (user said "run and report", "what's price-spy saying", or the cron instruction explicitly asked for output):** If nothing is notable, output the full watchlist table. The user is requesting information, so deliver it.
- **Never combine `[SILENT]` with content.** Either respond with `[SILENT]` exclusively, or produce a proper report — never both.

**How to decide which mode a cron job is running in:** Read the cron instruction carefully. If it says "silent" or "run only", use `[SILENT]`. If it says "report" or "run and report" or explicitly defines table output, produce the table instead. The user's instruction overrides the default.

### 3. Run and Report — scrape, update, then interpret
Combine run + report. Run first (update the data), then immediately read and interpret.

Used when the user says "run price-spy and report back" or "what's price-spy saying — go check"

- **Search Failure & Fallback:** If `web_extract` or `browser_navigate` fails due to timeout or bot detection (common on Amazon), do NOT retry the same URL immediately. Pivot to `web_search` with the product name and ASIN (e.g., `site:amazon.co.uk "Product Name" B0... price`) to extract snippets from search results.
- **Reporting Stability:** If the iteration limit is reached or browser tools are failing, prioritize reporting the "notable" updates based on whatever metadata or search snippets were successfully retrieved.

## Alert Rules (fires during Run, not Report)
- `price_threshold`: alert when current price < target_price
- `availability_watch`: alert when item appears in any tracked `conditions`
  - **This includes re-appearance.** If the last logged entry for an item/variant had `price: null` (was unavailable) and the current check finds a price in a tracked condition, that IS an availability_watch trigger. You don't need the item to be brand-new-to-the-list — re-appearance after any period of unavailability counts.
- **Sustained Low Stock Urgency:** For archive or limited-edition items, prioritize reporting when stock drops from 2 to 1. This is a critical signal that the item is nearly gone.
- Item disappeared: alert with context about why it might be gone
- Item re-appeared: alert when a previously unavailable item (price was null for 1+ consecutive checks) becomes available again. Include how many days it was gone and the new price. For multi-variant products, note if ALL variants returned simultaneously — that's a supply-side event (warehouse restock, new seller batch), not a lucky find.
- No alert for stable prices or no-change (don't cry wolf)

**WhatsApp alert format:**
```
🔔 Price Spy alert

[Item name]
Now: £XX.XX ([condition])
Target: £XX.XX
[URL]

Want me to add to basket? (Amazon only)
```

## Commands

### add
Add a new item to the watchlist. Requires:
- `name` — product name
- `url` — product page URL
- `price_source` — which skill checks the price (`"amazon"`, or `null` for best-efforts)
- `tracking_mode` — `"price_threshold"` or `"availability_watch"`
- `target_price` — for price_threshold mode (GBP)
- `conditions` — array of conditions to track: `["new"]`, `["used_very_good"]`, `["new", "used_very_good"]`
- Optional: `variants` array for multi-variant products
- Optional: `asin` for Amazon products
- Optional: `last_paid` what the user previously paid

Auto-generate `id` from name (slugified). Set `active: true`, `added: today`, empty `price_history`.

### list
Show all active items with last known price and alert status. Full watchlist — not filtered by importance.

### remove <item_id>
Mark item as inactive (soft delete). Don't remove from JSON, set `active: false`.

### pause <item_id> / resume <item_id>
Toggle `active` flag.

## Items JSON Schema

Located at: `items.json` in this skill directory.

```json
{
  "schema_version": 1,
  "items": [
    {
      "id": "string (slug, unique)",
      "name": "string",
      "url": "string (full URL)",
      "asin": "string | null (Amazon only)",
      "price_source": "string | null (skill name, e.g. 'amazon')",
      "tracking_mode": "price_threshold | availability_watch | price_threshold_with_availability",
      "target_price": "number | null (GBP)",
      "last_paid": "number | null (GBP)",
      "currency": "string (default: GBP)",
      "conditions": ["new", "used_very_good", "used_good", "used_acceptable"],
      "variants": [
        {
          "label": "string",
          "style_name": "string | null (Amazon variant selector value)",
          "asin": "string | null",
          "size": "string | null",
          "target_price": "number | null (per-variant target)"
        }
      ],
      "price_history": [
        {
          "date": "YYYY-MM-DD",
          "condition": "string",
          "price": "number | null (null means item was unavailable / no price found on that check)",
          "variant": "string | null",
          "observation": "string | null (contextual notes: stock levels, trends, sale indicators, page changes, etc.)"
        }
      ],
      "added": "YYYY-MM-DD",
      "active": "boolean",
      "notes": "string | null"
    }
  ]
}
```

### Extensibility
The schema is designed to be extended. Future additions may include:
- `notify_channel` — override default WhatsApp delivery
- `check_frequency` — per-item cron overrides
- `price_drop_percent` — alert on % change rather than absolute threshold
- `competitor_urls` — track same product across multiple retailers
- `tags` — group items (e.g. "coffee", "spirits", "clothing")
- `max_price` — alert if price goes ABOVE a threshold (e.g. rent, subscriptions)

When adding new fields, bump `schema_version` and make them optional with sensible defaults.

## User Preferences (the user)

### Preference: Clean-slate context when revisiting projects
When the user revisits an ongoing project or topic he has previously discussed with Araminta, **he wants a clean slate** — he explicitly does not want the conversation to anchor on or reference prior sessions unless he specifically asks for that history. This means:

- When the user says "let's look at beanz.com again" or revisits any tracked product/domain, **treat it as a fresh inquiry** — ask for current requirements rather than assuming continuity from a previous conversation.
- Do NOT lead with "Last time we discussed..." or "As we established in the earlier session..." unless the user explicitly asks for historical context.
- Do NOT carry forward assumptions from prior sessions (e.g., "You previously preferred X, so I assumed Y") — re-confirm preferences each time.
- This preference applies particularly to recurring shopping/research tasks where the user's needs may have shifted.

**Why this matters:** the user finds conversational anchoring on stale context to be unhelpful and slightly presumptuous. He prefers efficiency over conversational continuity across sessions.

**When to break this rule:** Only when the user explicitly says "what did we decide last time?" or "remind me where we left off." Otherwise, start fresh.

---

## Basket Suggestion
When an alert fires for an Amazon item (`price_source: "amazon"`), include in the WhatsApp message:
> "Want me to add to your basket?"

If the user says yes, use the Amazon skill's existing Add to Basket functionality.
Never complete a purchase. Basket only.

## Price Source Resolution
1. If `price_source` is set → call that skill's price-check function
2. If `price_source` is null → best-efforts anti-detection browser scrape of `url`
3. If skill call fails → fall back to anti-detection browser scrape
4. If all fails → log error, skip item, don't alert

### anti-detection browser Failure & Web-Extract Fallback Chain
anti-detection browser (browser_navigate) can fail intermittently — CDP timeouts, Page.enable failures, or auto-launch errors. When this happens, do NOT retry the same URL repeatedly. Instead, use this multi-layered fallback chain:

1. **web_extract (first)** — try `web_extract(urls=[url])` directly. This often works when anti-detection browser does not, as it uses a different scraping backend. It may return a truncated but usable product summary with pricing information embedded in the structured content.
2. **web_search (second)** — search for `site:amazon.co.uk "Product Name" ASIN price` or `site:retailer.com product-name £`. Extract snippets from search results. For Amazon, PriceRunner and other comparison sites sometimes surface current prices in search snippets.
3. **Price comparison sites (third)** — If Amazon-specific search results don't surface a price, try IdealO (idealo.co.uk) or PriceRunner. These aggregate merchant prices and often show Amazon's current price plus free delivery status. Example: `idealo.co.uk/compare/5129196/arran-10-years-46.html` for a whisky. The structured data here includes exact price, delivery cost, and a note if Amazon is the seller with free Prime delivery.
4. **web_extract again (fourth)** — after searching, re-`web_extract` the same URL. Sometimes the page loads differently on second attempt or from a different referral context.
5. **Skip item** — log the issue in `observation` with the exact error message and move on.

**Pitfall — web_extract Amazon availability false negatives:** The AI-generated summary in `web_extract` output sometimes includes a line like "No featured offers available at time of capture" even when the product IS in stock and has a live price. This happens because the summary AI hallucinates availability status based on incomplete DOM parsing. Never conclude an item is unavailable based solely on such a statement in the web_extract summary text. Instead:
- Look for actual price data in the structured content (pricing tables, "One-Time Purchase", "£44.00" mentions)
- Cross-reference with search snippets or price comparison sites
- If the structured content contains price data AND a conflicting "no featured offers" claim, trust the structured price data
- The canonical test: if you can see a price figure AND a "One-Time Purchase" option in the extract, the item is available regardless of any "no featured offers" text

**Pitfall — USD vs GBP on amazon.co.uk:** web_extract results from Amazon may show prices in USD (especially for Amazon Global Store items sold from US). Check the currency context in the extracted content — look for USD vs £/GBP indicators. The product listing may say "$66.06" even on amazon.co.uk if the seller is Amazon US Global. When this happens:
- The product may still have a UK buy-box price that search snippets show in GBP
- Cross-reference the ASIN with idealo or search results to get the GBP price
- Log both the USD price from page extraction AND the GBP price from search results in the observation

## Product Disappearance
When a product URL stops working or the listing appears dead:
1. **Search for the product** — use the product name, brand, ASIN to find it on the same retailer or elsewhere
2. **If found under a new URL/ASIN** → update the item's `url`/`asin` fields and note the change in `price_history`
3. **If genuinely gone** → log it with a reasoned observation about *why*. Consider:
   - Was stock low last time you checked? (e.g. "only 2 left" → probably sold out)
   - Was it a sale/clearance item? (might have been a one-off)
   - Is the brand still selling other products? (product discontinued vs. seller gone)
   - Is there a replacement product? (new model, rebranded listing)
4. **Alert the user** with the context: "The [product] appears to have been delisted — last check showed only 2 left. Likely sold out."

- **Urgency tracking:** Note when stock levels drop to critically low numbers (e.g., 1 or 2 left) for archive or limited-edition items, as this often precedes permanent unavailability.

**What to note:** anything that could be useful context for the NEXT check or for the report interpretation:
- Stock levels ("only 2 left", "in stock with 15+ sellers")
- Price trend ("down from £42.50 last week", "on sale at 40% off RRP")
- Condition availability ("used-very-good appeared for the first time")
- Variant changes ("new colour variant added", "1.2L now out of stock")
- Seller behaviour ("price fluctuates £3-5 daily", "Subscribe & Save available at 15% off")
- Sale indicators ("clearance", "limited time deal", "Prime Day pricing")
- Page changes ("listing redesigned", "different seller in buy box")

**DOM-based price extraction (canonical source of truth):**
For Amazon, a reliable extraction pattern is:
- Price: `document.querySelectorAll(".a-price .a-offscreen")[0]?.textContent`
- Availability: `document.querySelector("#availability span")?.textContent?.trim()`
Trust these DOM selectors over `web_extract` summaries, which can hallucinate unavailability ("no featured offers") even when the buy-box is live.

A real example: the Normcore White tamper (B0GCG5HN29) was unavailable for 4 days. web_extract returned empty content. `browser_navigate` loaded the page, and `browser_console` showed £48.67 with "In stock" — a meaningful re-appearance that web_extract would have missed entirely.

- **No Python Scripting for Browser Tools:** Do not attempt to import `browser_navigate`, `browser_console`, or other browser tools inside an `execute_code` block. These tools are not exported via `hermes_tools` in the sandbox and will cause `ImportError`. You MUST call these tools as top-level agent actions.
- **Execution Constraints:** When running as a cron job, `execute_code` may be blocked by security policies. In these cases, use `patch()` with highly specific anchors to update the JSON data. If `patch()` fails due to anchor collisions or pagination warnings, use `read_file` (without offset/limit) to get a fresh view of the file before attempting the patch again.
- **DOM-based price extraction (canonical source of truth):**
For Amazon, a reliable extraction pattern is:
- Price: `document.querySelectorAll(".a-price .a-offscreen")[0]?.textContent`
- Availability: `document.querySelector("#availability span")?.textContent?.trim()`
Trust these DOM selectors over `web_extract` summaries, which can hallucinate unavailability ("no featured offers") even when the buy-box is live.

## Updating items.json (critical)

### Recommended strategy: patch(), not full-file rewrite
The `items.json` file accumulates data over time and can reach 500+ lines. **Do not rewrite the entire file each session.** Instead, use `patch()` to append new `price_history` entries by targeting a unique text anchor near the insertion point.

**How to patch:**
1. Read the file first (or use `read_file` with the known path: `items.json (in skill directory)`)
2. Identify an anchor: the closing `]` bracket of the last `price_history` entry for the item you're updating, or a nearby unique line like `"added": "YYYY-MM-DD"`
3. Use `path` to the full items.json path, and `old_string`/`new_string` with enough context for uniqueness (include a few lines before and after the insertion point)
4. Verify JSON validity with a quick Python check:
   ```
   python3 -c "import json; json.load(open('items.json'))"
   ```

**Pitfall: offset/limit partial reads.** If you read the file with `offset`/`limit` pagination (because it's large), `patch()` may warn about reading a stale partial view. To avoid this, either:
- Read the whole file in one go (use a higher limit), or
- Accept the warning but verify with the Python check above after patching

**Pitfall — JSON Patching vs. Full Rewrite**
- When updating `items.json`, `patch()` may fail if the `old_string` anchor is not perfectly unique (e.g., multiple variants have identical observations). 
- If targeting the end of a `price_history` array, use the combined sequence of the last entry's date/variant plus the closing bracket of the array to ensure a unique anchor.
- If `patch()` fails repeatedly due to anchor collisions or pagination warnings, use `execute_code` to load, modify, and `json.dump()` the entire file to guarantee integrity. **Note:** In cron-job mode, `execute_code` may be blocked by security policies unless explicitly trusted; in such cases, use highly specific `patch()` anchors or request a manual override.
- **Crucial:** When applying patches to large files read with pagination (offset/limit), be aware that the agent may receive "stale partial view" warnings. Always verify the final state of the JSON file with a validity check (`python3 -c "import json; json.load(open('items.json'))"`) to ensure the structural integrity of the array hasn't been compromised by a misaligned patch.

- **JSON Integrity Risk — patch() duplication bug:** When updating `items.json` in cron-job mode, avoid `execute_code` as it may be blocked by security policies. While `patch()` is the preferred method, be extremely cautious with anchors. **Critical failure mode:** If `patch()` is called with an `old_string` that matches multiple locations (e.g., identical price_history entries across different items or variants), it will apply the same insertion at every match, duplicating the new entry N times and breaking the JSON array structure. This produced 3,000+ lines of corrupted data in June 2026.
  - **Prevention:** Always read the full file first (`read_file` without offset/limit) to verify anchor uniqueness. Use compound anchors: last entry's date + variant + the closing `]` of that specific item's price_history array.
  - **Detection:** After any patch, run `python3 -c "import json; json.load(open('items.json'))"` immediately. If it fails, the file is corrupted — stop and recover manually in a non-cron session.
  - **Recovery:** If corruption is detected, do NOT attempt further blind patches. Rewrite the entire file from a known-good backup or reconstruct from the last clean version.

- **DOM Leakage:** When checking multiple items in a loop, console-based price extraction can occasionally return the value of the previous page if the DOM hasn't updated. Always verify that `browser_navigate` completed and the page title matches the expected item before executing extraction scripts.

## Cron Setup
Daily cron job that runs `run` for all items.
- Runs silently, updates `items.json`
- Sends alert ONLY if an alert condition is met (via Telegram primary, WhatsApp fallback)
- Total silence otherwise (respond with exactly `[SILENT]`)
- Admin brief can trigger a separate `report` to pull notable items into the daily summary

**Cron job configuration requirements:**
- `deliver: "telegram:<numeric_chat_id>"` — explicit numeric Telegram chat ID, not a display name
- `prompt` must include "silent mode" or "run only" instruction so the worker knows to emit `[SILENT]` when nothing notable
- `enabled_toolsets` must include `["send_message", "web", "terminal", "file", "browser"]` for alert delivery and scraping
- Do NOT use `deliver: "telegram,discord"` — simultaneous multi-target delivery defeats the silent-mode suppression. The scheduler delivers to ALL listed targets unconditionally.
- Do NOT use `deliver: "origin"` for cron jobs — it resolves to the creating chat which may be Discord.

## References
- `references/cron-job-configuration.md` — Cron job configuration patterns for silent-mode vs report-mode runs, Telegram chat ID usage, toolset requirements, and delivery target rules
- `references/amazon-unavailability-patterns.md` — how to detect and report "No featured offers available" vs "Currently unavailable" vs genuine delisting on Amazon UK
- `references/browser-extraction.md` — DOM selectors and consent-handling patterns that worked for Amazon and Shopify product pages
- `references/shopify-collection-fallback.md` — Fallback price verification for Shopify product pages that fail web_extract due to page size (e.g. campbellsofbeauly.com); uses search snippets and collection pages instead
- `references/pi-zero-2w-multi-source-tracking.md` — multi-source stock+price tracking pattern (Pi Hut, Pimoroni Shopify + Amazon search; tracking_mode: stock_and_price vs price_threshold; re-appearance detection on Shopify)
- `references/algolia-retail-api-discovery.md` — How to discover and query embedded Algolia search APIs on Next.js retail sites. Faster and more reliable than browser scraping for SPA product listings.
- `references/extraction-edge-cases.md` — Detailed edge cases on idealo cross-referencing, cached-vs-live price discrepancy, alternate URL formats, consecutive-day stale unavailability suppression, USD pricing on amazon.co.uk (Global Store shift), and multi-retailer pricing context. (Absorbed from `price-spy-practical-notes`.)

## Practical extraction notes (absorbed from `price-spy-practical-notes`)

### Reliable extraction heuristics
- On Amazon pages, the quickest reliable price read is often `span.a-price span.a-offscreen`.
- If the desktop URL is captcha-blocked, try the mobile page form first: `https://www.amazon.co.uk/gp/aw/d/ASIN`.
- Confirm stock with plain-text cues such as `In stock`, `Only X left`, or `Currently unavailable`.
- Treat variant pages separately; do not assume a parent listing price applies to every size/color.
- If a page repeats several prices, prefer the first valid active-variant price and verify it against page text.
- For non-Amazon retailers, page-text extraction is usually enough if the page is cleanly rendered.

### What to record in observations
Always capture context alongside price: stock level or scarcity, sale/clearance markers, condition availability, variant changes, page/listing changes, whether the listing appears stable or choppy.

### Reporting discipline
Only surface notable movements: threshold crossings, significant price moves, low stock, appearance/disappearance, used-condition availability, or URL changes. Do not mention stable prices or items with ample stock. In silent cron-style runs, if nothing notable happened, return exactly `[SILENT]`.

### Disappearance handling
If a URL dies or a listing seems gone: search by product name and ASIN. If relocated, update URL/ASIN and note it. If genuinely gone, explain the likely reason in the observation, especially if the last check showed low stock.

### Fallback chain when anti-detection browser fails
1. **web_extract** — try both `/dp/ASIN` and full product-path URL formats.
2. **web_search** — search `site:amazon.co.uk "Product Name" ASIN price` for search snippets.
3. **Idealo** — for whisky, coffee, and commodity products, idealo.co.uk/compare/* gives structured per-merchant pricing tables.
4. **Re-extract** — try web_extract again on the same URL; sometimes the page loads differently on second attempt.

## Variant reporting (absorbed from `price-spy-variant-reporting`)

### Why this exists
A naive item-level comparison of the last two `price_history` entries can produce false deltas when variants are checked in rotation. The history needs to be compared per variant.

### Workflow
1. Read `items.json`.
2. For each active item:
   - If the item has variants, group `price_history` by `variant`.
   - Compare each variant only against its own previous entry.
   - Ignore changes that are just another variant being checked.
3. Report only meaningful changes:
   - price below target
   - price change of £2+ or 5%+
   - low stock (≤3 remaining)
   - used condition appears
   - URL/ASIN changes
4. When scraping Amazon pages, prefer:
   - buy-box price from `corePriceDisplay_desktop_feature_div` or `corePrice_feature_div`
   - stock text from the page body (`In stock`, low-stock wording, seller text)
   - seller/source text for context in `observation`
5. Record one history entry per variant with a clear `variant` label and a contextual `observation`.

### Pitfalls
- Do not compare interleaved variant entries as if they were one series.
- Do not treat the presence of other seller offers as a price drop unless the buy box or tracked offer actually changed.
- Do not report stable prices, plentiful stock, or unchanged variants.

### Verification
Before reporting, sanity-check that each notable item is notable for the same variant, not because another variant was checked in between.
