#!/usr/bin/env python3
"""
beanz-query.py — Query beanz.com UK coffee catalog via Algolia API.

Usage:
    python beanz-query.py [--save] [--roast dark|medium|all] [--max-price N]

Default filter profile:
    - Bag Size: 1 kg
    - Brew Method: Espresso
    - Caffeine: Caffeinated (No = not decaf)
    - Roast: Medium Roast + Darker Roast

Outputs a table sorted by price (low to high).
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Beanz embeds its public, read-only Algolia configuration in the catalogue page.
# Discover it for each run rather than shipping a stale key in the package.
def discover_algolia_config() -> tuple[str, str, str]:
    request = urllib.request.Request(
        "https://www.beanz.com/en-gb/coffee",
        headers={"User-Agent": "Mozilla/5.0 (compatible; BeanzShopping/1.0)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        storefront = response.read().decode("utf-8", errors="replace")

    def field(name: str) -> str:
        match = re.search(rf'"{name}":"([^"\\]+)"', storefront)
        return match.group(1) if match else ""

    app_id = field("algolia_app_id")
    api_key = field("algolia_search_api_key")
    index = field("algolia_index_name") or "Beanz_UK"
    if not app_id or not api_key:
        raise RuntimeError("Beanz storefront did not expose usable Algolia catalogue configuration.")
    return app_id, api_key, index


ALGOLIA_APP_ID, ALGOLIA_API_KEY, ALGOLIA_INDEX = discover_algolia_config()
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

# Default filter profile
DEFAULT_FILTERS = [
    ["WEB_BAGSIZE_en_GB:1 kg"],
    ["Brew_method:Espresso"],
    ["Looking_for_Decaf:No"],
    ["The_Roast:Medium Roast", "The_Roast:Darker Roast"],
]

ROAST_OPTIONS = {
    "dark": [["The_Roast:Darker Roast"]],
    "medium": [["The_Roast:Medium Roast"]],
    "all": [["The_Roast:Medium Roast", "The_Roast:Darker Roast"]],
}


def query_algolia(filters, max_price=None):
    """Query Algolia and return parsed hits."""
    payload = {
        "query": "",
        "facetFilters": filters,
        "hitsPerPage": 100,
        "attributesToRetrieve": [
            "productName",
            "Our_Roasters",
            "displayPrice",
            "unit_pricing",
            "The_Roast",
            "Coffee_Flavors",
            "WEB_TASTING_NOTES_en_GB",
            "Blend_or_Single_Origin",
            "PDP_URL",
            "productDescription",
        ],
    }

    req = urllib.request.Request(
        ALGOLIA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    hits = data.get("hits", [])
    parsed = []

    for h in hits:
        price_str = h.get("displayPrice", "0").replace("£", "").replace(",", "")
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0

        if max_price is not None and price > max_price:
            continue

        notes = h.get("WEB_TASTING_NOTES_en_GB", [])
        notes_str = " | ".join(notes) if notes else h.get("Coffee_Flavors", "?")

        parsed.append(
            {
                "name": h.get("productName", "?"),
                "roaster": h.get("Our_Roasters", "?"),
                "price": price,
                "roast": h.get("The_Roast", "?"),
                "type": h.get("Blend_or_Single_Origin", "?"),
                "notes": notes_str,
                "url": h.get("PDP_URL", ""),
                "description": h.get("productDescription", ""),
            }
        )

    parsed.sort(key=lambda x: x["price"])
    return parsed


def render_markdown(coffees):
    """Render coffees as a markdown table."""
    lines = []
    lines.append(f"| Price/kg | Coffee | Roaster | Roast | Type | Tasting Notes |")
    lines.append(f"|---|---|---|---|---|---|")

    for c in coffees:
        price = f"£{c['price']:.2f}"
        name = c["name"].replace("|", "\\|")
        roaster = c["roaster"].replace("|", "\\|")
        roast = c["roast"].replace("|", "\\|")
        type_ = c["type"].replace("|", "\\|")
        notes = c["notes"].replace("|", "\\|")
        lines.append(f"| {price} | {name} | {roaster} | {roast} | {type_} | {notes} |")

    return "\n".join(lines)


def render_terminal(coffees):
    """Render coffees as a compact terminal table."""
    lines = []
    lines.append(
        f"{'Price':>7}  {'Coffee':<35} {'Roaster':<20} {'Roast':<14} {'Type':<10} Tasting Notes"
    )
    lines.append(
        f"{'='*7}  {'='*35} {'='*20} {'='*14} {'='*10} {'='*50}"
    )

    for c in coffees:
        price = f"£{c['price']:.2f}"
        name = c["name"][:34]
        roaster = c["roaster"][:19]
        roast = c["roast"][:13]
        type_ = c["type"][:9]
        notes = c["notes"][:48]
        lines.append(
            f"{price:>7}  {name:<35} {roaster:<20} {roast:<14} {type_:<10} {notes}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Query beanz.com UK coffee catalog")
    parser.add_argument(
        "--roast", choices=["dark", "medium", "all"], default="all",
        help="Roast filter (default: dark+medium)"
    )
    parser.add_argument(
        "--max-price", type=float, default=None,
        help="Maximum price per kg"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save output to a dated markdown file in ./snapshots/"
    )
    parser.add_argument(
        "--format", choices=["markdown", "terminal"], default="terminal",
        help="Output format (default: terminal)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON instead of table"
    )
    args = parser.parse_args()

    # Build filter set
    filters = [
        ["WEB_BAGSIZE_en_GB:1 kg"],
        ["Brew_method:Espresso"],
        ["Looking_for_Decaf:No"],
    ]
    filters.extend(ROAST_OPTIONS[args.roast])

    coffees = query_algolia(filters, max_price=args.max_price)

    if args.json:
        output = json.dumps(coffees, indent=2)
    elif args.format == "markdown":
        output = render_markdown(coffees)
    else:
        output = render_terminal(coffees)

    # Header
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    roast_label = {"dark": "Darker", "medium": "Medium", "all": "Medium + Darker"}[args.roast]
    header = (
        f"beanz.com UK — {len(coffees)} coffees\n"
        f"Filters: 1kg | Espresso | Caffeinated | {roast_label} Roast"
    )
    if args.max_price:
        header += f" | Max £{args.max_price:.2f}"
    header += f"\nQueried: {now}\n"

    full_output = f"{header}\n{output}\n\nCheapest: £{coffees[0]['price']:.2f} ({coffees[0]['name']}) | Most expensive: £{coffees[-1]['price']:.2f} ({coffees[-1]['name']})"

    print(full_output)

    if args.save:
        snap_dir = Path(__file__).parent / "snapshots"
        snap_dir.mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = snap_dir / f"beanz_{ts}.md"
        filename.write_text(full_output, encoding="utf-8")
        print(f"\n[saved to {filename}]")


if __name__ == "__main__":
    main()