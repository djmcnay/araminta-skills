#!/usr/bin/env python3
"""
Query an Algolia-backed retail site for product catalog data.

Usage:
    python3 scripts/algolia-retail-query.py discover <product-listing-url>
    python3 scripts/algolia-retail-query.py query <product-listing-url> --facet "FIELD:value"
    python3 scripts/algolia-retail-query.py query <product-listing-url> --sort "field" --facet "FIELD:value"

Example (beanz.com — 1kg dark roast espresso coffees sorted by price):
    python3 scripts/algolia-retail-query.py query \
        "https://www.beanz.com/en-gb/coffee" \
        --facet "WEB_BAGSIZE_en_GB:1 kg" \
        --facet "Brew_method:Espresso" \
        --facet "Looking_for_Decaf:No" \
        --attributes "productName,Our_Roasters,displayPrice,unit_pricing,The_Roast,Coffee_Flavors,PDP_URL"

Output: JSON to stdout, one hit per line.
"""

import json
import sys
import urllib.request
import urllib.parse
import argparse
import re


def extract_algolia_config(html: str) -> dict:
    """Search __NEXT_DATA__ for Algolia credentials."""
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
    if not m:
        return {}
    data = json.loads(m.group(1))
    props = data.get("props", {}).get("pageProps", {})
    config = props.get("config", {})
    return {
        "app_id": config.get("algolia_app_id"),
        "search_key": config.get("algolia_search_api_key"),
        "index_name": config.get("algolia_index_name"),
        "filter_props": config.get("algolia_filter_props", []),
        "raw": config,
    }


def discover(url: str) -> dict:
    """Probe a URL for embedded Algolia config."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    config = extract_algolia_config(html)
    if not config.get("app_id"):
        print(f"No Algolia config found at {url}", file=sys.stderr)
        return {}
    print(json.dumps(config, indent=2))
    # Show a quick test query
    if config.get("index_name"):
        test_query(config["app_id"], config["search_key"], config["index_name"])
    return config


def test_query(app_id: str, search_key: str, index_name: str):
    """Show a sample hit to reveal field names."""
    algolia_url = f"https://{app_id}-dsn.algolia.net/1/indexes/{index_name}/query"
    payload = {
        "query": "",
        "hitsPerPage": 1,
        "attributesToRetrieve": ["*"],
    }
    req = urllib.request.Request(
        algolia_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-Algolia-Application-Id": app_id,
            "X-Algolia-API-Key": search_key,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("hits"):
        print("Sample hit fields:", list(result["hits"][0].keys())[:15])
        print(json.dumps(result["hits"][0], indent=2)[:800])


def run_query(url, facets, sort_field, attributes, hits_per_page=100):
    """Execute a targeted Algolia query."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    config = extract_algolia_config(html)
    if not config.get("app_id"):
        print(f"No Algolia config found at {url}", file=sys.stderr)
        sys.exit(1)

    app_id = config["app_id"]
    search_key = config["search_key"]
    index_name = config["index_name"]
    algolia_url = f"https://{app_id}-dsn.algolia.net/1/indexes/{index_name}/query"

    facet_filters = [[f] for f in facets]
    payload = {
        "query": "",
        "facetFilters": facet_filters,
        "hitsPerPage": hits_per_page,
    }
    if attributes:
        payload["attributesToRetrieve"] = attributes.split(",")
    if sort_field:
        payload["sortFacetValuesBy"] = sort_field

    req = urllib.request.Request(
        algolia_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-Algolia-Application-Id": app_id,
            "X-Algolia-API-Key": search_key,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    for hit in result.get("hits", []):
        print(json.dumps(hit))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["discover", "query"])
    parser.add_argument("url")
    parser.add_argument("--facet", action="append", default=[])
    parser.add_argument("--sort")
    parser.add_argument("--attributes")
    parser.add_argument("--hits", type=int, default=100)
    args = parser.parse_args()

    if args.command == "discover":
        discover(args.url)
    else:
        run_query(args.url, args.facet, args.sort, args.attributes, args.hits)


if __name__ == "__main__":
    main()
