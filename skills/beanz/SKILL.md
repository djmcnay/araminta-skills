---
name: beanz
description: Browse and purchase specialty coffee from beanz.com. Query the catalog via Algolia API, add items to cart, and extract order history. Works with any persistent browser session.
ownership: collab
version: 1.0.0
author: Araminta
license: MIT
tags: [coffee, beanz, shopping, algolia, playwright]
category: shopping
---

# beanz — Specialty Coffee Purchasing

Browse and purchase coffee from beanz.com (UK). The site uses an Algolia search backend, which makes catalog queries fast and reliable without browser scraping. A Playwright CLI handles cart operations via a persistent browser session.

## When to use

- The user wants to browse, search, or filter beanz.com coffee catalog
- The user wants to add coffee to cart (one-time or subscription)
- The user wants to compare prices per kg across roasts, roasters, or brew methods
- The user wants to extract order history from confirmation emails

## Architecture

```
beanz-query.py        — Query catalog via Algolia API (no browser needed)
beanz-basket-cli.js    — Add to cart via Playwright + persistent browser
extract_orders.py      — Parse order history from Gmail confirmation emails
```

## Algolia API

beanz.com embeds Algolia credentials in its page HTML. These are public application-level keys (not secrets), safe to use for read-only catalog queries.

### Configuration

Copy `config.example.json` to `config.json` and fill in the values:

```bash
cp config.example.json config.json
```

Or set environment variables:

```bash
export BEANZ_ALGOLIA_APP_ID="<your-app-id>"
export BEANZ_ALGOLIA_API_KEY="<your-api-key>"
export BEANZ_ALGOLIA_INDEX="Beanz_UK"
```

### Discovery

To discover Algolia credentials for beanz.com (or any Algolia-backed retailer):

```bash
python3 price-spy/scripts/algolia-retail-query.py discover "https://www.beanz.com/en-gb/coffee"
```

### Endpoint

```
https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX}/query
```

### Catalog query (beanz-query.py)

```python
import json, urllib.request
from pathlib import Path

# Load credentials from config.json
config_path = Path(__file__).parent / "config.json"
with open(config_path) as f:
    cfg = json.load(f)

ALGOLIA_URL = f"https://{cfg['algolia_app_id']}-dsn.algolia.net/1/indexes/{cfg['algolia_index']}/query"

payload = {
    "query": "",
    "facetFilters": [
        ["WEB_BAGSIZE_en_GB:1 kg"],
        ["Brew_method:Espresso"],
        ["Looking_for_Decaf:No"],
    ],
    "hitsPerPage": 100,
    "attributesToRetrieve": [
        "productName", "Our_Roasters", "displayPrice", "unit_pricing",
        "The_Roast", "Coffee_Flavors", "WEB_TASTING_NOTES_en_GB",
        "Blend_or_Single_Origin", "PDP_URL", "productDescription",
    ],
}

req = urllib.request.Request(
    ALGOLIA_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "X-Algolia-Application-Id": cfg["algolia_app_id"],
        "X-Algolia-API-Key": cfg["algolia_api_key"],
        "Content-Type": "application/json",
    },
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))
```

### Available facets

| Facet | Key | Example values |
|-------|-----|----------------|
| Bag size | `WEB_BAGSIZE_en_GB` | `1 kg`, `250 gr`, `200 gr` |
| Brew method | `Brew_method` | `Espresso`, `Filter`, `All methods` |
| Decaf | `Looking_for_Decaf` | `Yes`, `No` |
| Roast | `The_Roast` | `Light Roast`, `Medium Roast`, `Darker Roast` |
| Roaster | `Our_Roasters` | (roaster name) |
| Type | `Blend_or_Single_Origin` | `Blend`, `Single Origin` |

### CLI usage

```bash
# Search all 1kg espresso coffees, medium + dark roast
python beanz-query.py

# Dark roast only, max £40/kg
python beanz-query.py --roast dark --max-price 40

# Save to snapshots/ as markdown
python beanz-query.py --save --format markdown

# Output raw JSON
python beanz-query.py --json
```

## Basket CLI (beanz-basket-cli.js)

Uses Playwright to connect to a persistent browser session and add coffee to cart. Requires Playwright installed.

### Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `BEANZ_CDP_URL` | `http://localhost:9222` | CDP endpoint for persistent browser |

### Usage

```bash
# Add a coffee by name (searches Algolia to resolve URL)
node beanz-basket-cli.js "Ethiopia Yirgacheffe"

# Add by PDP URL
node beanz-basket-cli.js "https://www.beanz.com/en-gb/coffee/some-coffee.html"

# One-time purchase, 1kg, whole bean
node beanz-basket-cli.js "Ethiopia Yirgacheffe" --size 1000 --grind "Whole bean"

# Subscription, 2-weekly, 2 bags
node beanz-basket-cli.js "Ethiopia Yirgacheffe" --subscription --freq 2 --bags 2

# Add two different coffees
node beanz-basket-cli.js "Ethiopia Yirgacheffe" --second "Colombia Huila"

# Dry run (configure but don't click add)
node beanz-basket-cli.js "Ethiopia Yirgacheffe" --dry-run

# Full checkout flow (stops at payment page)
node beanz-basket-cli.js "Ethiopia Yirgacheffe" --checkout
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--checkout` | off | Continue to checkout, stop at payment page |
| `--subscription` | off | Order as subscription instead of one-time |
| `--grind <name>` | `Whole bean` | `Whole bean` or `Ground` |
| `--size <grams>` | `1000` | `250` or `1000` |
| `--bags <n>` | `1` | Number of bags (max 5) |
| `--freq <weeks>` | `2` | Subscription frequency: 1,2,4,6,8 |
| `--second <product>` | none | Add a 2nd coffee to cart |
| `--show` | off | Bring page to front (for VNC viewing) |
| `--dry-run` | off | Configure but don't click add |

## Order history extraction (extract_orders.py)

Parses beanz.com order confirmation emails from Gmail via Google Workspace API. Uses the Algolia catalog to split coffee name from roaster name (beanz emails combine them in one field).

Requirements:
- `gws` CLI (Google Workspace bridge) configured with Gmail scope
- Google OAuth token at `~/.hermes/google_token.json` or equivalent

```bash
python extract_orders.py
```

Outputs a summary table and saves raw data to `~/.beanz_order_history.json`.

## Pitfalls

- **Algolia keys are public but rate-limited.** Don't hammer the API. One query per session is plenty.
- **Cart authentication.** The basket CLI needs a logged-in browser session. If the persistent browser isn't authenticated, cart operations will redirect to login.
- **25% discount detection.** The cart CLI checks for a "25% off" line in the cart. This is a beanz.com loyalty discount (e.g. Sage appliance owner). If you don't have it, the CLI will warn but still proceed.
- **Free delivery threshold.** beanz.com offers free delivery above a threshold (varies). The CLI warns if delivery isn't free; add a second bag to qualify.
- **Gmail extraction needs gws.** The `extract_orders.py` script depends on the `gws` CLI being installed and authenticated. Skip it if you don't use Google Workspace.

## Adaptation notes

- **CDP port:** Change `BEANZ_CDP_URL` env var to match your persistent browser setup.
- **Gmail extraction:** If you use a different email provider, replace the `gws` calls with your own email API. The parsing logic (regex patterns for beanz email format) stays the same.
- **Region:** The Algolia index is `Beanz_UK`. For other regions, check beanz.com page source for the correct index name.