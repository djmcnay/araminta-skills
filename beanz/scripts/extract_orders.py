#!/usr/bin/env python3
"""Extract beanz.com order history from Gmail order confirmation emails.

Uses Algolia catalog to correctly split coffee name from roaster name.

Requirements:
    - gws CLI (Google Workspace bridge) installed and authenticated
    - Google OAuth token at HERMES_HOME/google_token.json or ~/.hermes/google_token.json

Usage:
    python extract_orders.py
"""

import json
import os
import re
import subprocess
import base64
import urllib.request
import urllib.parse
from pathlib import Path

# Algolia credentials loaded from config.json (see config.example.json)
import os
_config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
if os.path.exists(_config_path):
    with open(_config_path) as _f:
        _cfg = json.load(_f)
    ALGOLIA_APP_ID = _cfg["algolia_app_id"]
    ALGOLIA_API_KEY = _cfg["algolia_api_key"]
    ALGOLIA_INDEX = _cfg.get("algolia_index", "Beanz_UK")
else:
    ALGOLIA_APP_ID = os.environ.get("BEANZ_ALGOLIA_APP_ID", "")
    ALGOLIA_API_KEY = os.environ.get("BEANZ_ALGOLIA_API_KEY", "")
    ALGOLIA_INDEX = os.environ.get("BEANZ_ALGOLIA_INDEX", "Beanz_UK")
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"


def get_access_token():
    """Refresh and return a valid OAuth2 access token via gws bridge."""
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    token_data = json.loads((home / "google_token.json").read_text())
    params = urllib.parse.urlencode({
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(token_data["token_uri"], data=params)
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        os.environ["GOOGLE_WORKSPACE_CLI_TOKEN"] = result["access_token"]
        return result["access_token"]


def fetch_catalog():
    """Fetch UK catalog from Algolia to build name/roaster lookup."""
    payload = {
        "query": "",
        "hitsPerPage": 100,
        "attributesToRetrieve": ["productName", "Our_Roasters"],
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

    catalog = {}
    roasters = set()
    for h in data.get("hits", []):
        name = h.get("productName", "")
        roaster = h.get("Our_Roasters", "")
        if name and roaster:
            catalog[name.lower()] = roaster
            roasters.add(roaster.lower())

    return catalog, roasters


def gws_get(msg_id):
    """Retrieve full message from Gmail via gws CLI."""
    result = subprocess.run(
        [
            "gws", "gmail", "users", "messages", "get",
            "--params", f'{{"userId": "me", "id": "{msg_id}", "format": "full"}}',
            "--format", "json"
        ],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)


def get_text_body(msg):
    """Extract text from HTML body of a Gmail message."""
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])
    if not parts and payload.get("body", {}).get("data"):
        parts = [payload]

    html_body = ""
    for part in parts:
        if part.get("mimeType") == "text/html":
            body_data = part.get("body", {}).get("data", "")
            if body_data:
                html_body = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
                break

    if html_body:
        text = re.sub(r'<[^>]+>', ' ', html_body)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&ndash;', '-', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # fallback: try plain text
    for part in parts:
        if part.get("mimeType") == "text/plain":
            body_data = part.get("body", {}).get("data", "")
            if body_data:
                return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
    return ""


def split_name_roaster(text, catalog, known_roasters):
    """Split a raw name+roaster string using the catalog lookup."""
    text_lower = text.lower()

    # Try exact match first
    if text_lower in catalog:
        return text, catalog[text_lower], "exact"

    # Try longest prefix match
    words = text.split()
    for i in range(len(words), 0, -1):
        candidate = " ".join(words[:i]).lower()
        if candidate in catalog:
            roaster = catalog[candidate]
            return " ".join(words[:i]), roaster, "prefix"

    # Try suffix match (roaster at end)
    for i in range(len(words), 0, -1):
        candidate = " ".join(words[i:]).lower()
        if candidate in known_roasters:
            return " ".join(words[:i]).strip(), " ".join(words[i:]).strip(), "suffix"

    # Fallback: unknown — return as-is
    return text.strip(), "", "unknown"


def parse_orders(text):
    """Parse all items from an order confirmation email."""
    items = []
    text = text.replace('Â', '')  # Strip encoding artifacts

    # Split by item markers
    sections = re.split(r'(?:Order Summary:|Personalized message):\s*', text)

    for section in sections[1:]:
        section = section.strip()
        if not section:
            continue

        # Stop at "Subtotal", "eGift Card" or next item
        clean = section.split('Subtotal')[0].split('eGift Card')[0].strip()

        # Find "One-time purchase" as delimiter
        otp_match = re.search(r'(.+?)\s+One-time purchase', clean)
        if not otp_match:
            continue

        name_roaster_raw = otp_match.group(1).strip()

        # Extract price
        price_match = re.search(r'Price:\s*£([\d,.]+)', clean)
        price = float(price_match.group(1).replace(',', '')) if price_match else None

        # Extract discounted price (format: £X* £Y where Y is discounted)
        disc_match = re.search(r'£[\d,.]+\*\s*£([\d,.]+)', clean)
        disc_price = float(disc_match.group(1).replace(',', '')) if disc_match else price

        # Extract number of bags
        bags_match = re.search(r'Number of bags:\s*(\d+)', clean)
        bags = int(bags_match.group(1)) if bags_match else 1

        # Extract tasting notes
        notes = ""
        notes_match = re.search(r'Flavour notes:\s*(.+?)\s*Brew Method:', clean, re.IGNORECASE)
        if notes_match:
            notes = notes_match.group(1).strip()

        item = {
            "raw": name_roaster_raw,
            "price_per_kg": price,
            "discounted_price_per_kg": disc_price,
            "bags": bags,
            "tasting_notes": notes,
        }
        items.append(item)

    return items


def resolve_items(items, catalog, known_roasters):
    """Resolve raw item names using catalog lookup."""
    resolved = []
    for item in items:
        name, roaster, method = split_name_roaster(item["raw"], catalog, known_roasters)
        resolved.append({
            **item,
            "name": name,
            "roaster": roaster,
            "match_method": method,
        })
    return resolved


def main():
    print("Building catalog from Algolia...")
    catalog, known_roasters = fetch_catalog()
    print(f"  {len(catalog)} coffees in catalog, {len(known_roasters)} roasters")
    print()

    print("Fetching beanz.com order history from Gmail...")
    get_access_token()

    # Get all beanz messages
    result = subprocess.run(
        [
            "gws", "gmail", "users", "messages", "list",
            "--params", '{"userId": "me", "q": "from:beanz.com", "maxResults": 50}',
            "--format", "json"
        ],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    message_ids = [m["id"] for m in data.get("messages", [])]
    print(f"  {len(message_ids)} emails from beanz.com")

    # Process confirmation emails
    orders = []
    for msg_id in message_ids:
        msg = gws_get(msg_id)
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "")
        date = headers.get("Date", "")

        if "Order Confirmation" not in subject:
            continue

        body_text = get_text_body(msg)
        items = parse_orders(body_text)

        if not items:
            continue

        # Extract order number
        order_num_match = re.search(r'Order #\s*[:\s]?(\d+)', subject)
        order_num = order_num_match.group(1) if order_num_match else "unknown"

        # Extract totals
        total_match = re.search(r'Total\s*£?([\d,.]+)', body_text)
        total = float(total_match.group(1).replace(',', '')) if total_match else None

        discount_match = re.search(r'Discount\s*-£?([\d,.]+)', body_text, re.IGNORECASE)
        discount = float(discount_match.group(1).replace(',', '')) if discount_match else None

        resolved_items = resolve_items(items, catalog, known_roasters)

        orders.append({
            "order_num": order_num,
            "date": date[:16] if date else "unknown",
            "items": resolved_items,
            "total": total,
            "discount": discount,
        })

    print(f"  {len(orders)} order confirmations found")
    print()

    # Print summary
    print(f"=== BEANZ.COM ORDER HISTORY ===")
    print()

    all_items = []
    for order in sorted(orders, key=lambda x: x["date"]):
        print(f"Order #{order['order_num']} — {order['date']}")
        print(f"  Total paid: £{order['total']:.2f}" if order['total'] else "  Total: ?")
        if order.get('discount'):
            print(f"  Discount: -£{order['discount']:.2f}")

        for item in order["items"]:
            name = item["name"]
            roaster = item["roaster"] if item["roaster"] else "[unknown]"
            price = item["price_per_kg"]
            disc = item["discounted_price_per_kg"]
            notes = item.get("tasting_notes", "")
            bags = item["bags"]

            if item["match_method"] == "unknown":
                print(f"  ! {name}")
            else:
                print(f"  - {name} by {roaster}")

            if price:
                print(f"    List: £{price:.2f}/kg | Disc: £{disc:.2f}/kg | {bags} bag(s)")

            if notes:
                print(f"    Notes: {notes}")

            all_items.append({
                "order_num": order["order_num"],
                "date": order["date"],
                "name": name,
                "roaster": roaster,
                "price_per_kg": price,
                "discounted_price_per_kg": disc,
                "tasting_notes": notes,
                "bags": bags,
            })

        print()

    # Summary table
    print("\n=== ALL COFFEES ORDERED ===")
    print(f"{'Date':<12} {'Coffee':<25} {'Roaster':<18} {'List':>7} {'Disc':>7} {'Notes':<30}")
    print("-" * 95)

    seen = set()
    for item in all_items:
        key = (item["name"], item["roaster"], item["date"])
        if key in seen:
            continue
        seen.add(key)

        date = item["date"]
        name = item["name"][:24]
        roaster = item["roaster"][:17] if item["roaster"] else "[unknown]"
        price = f"£{item['price_per_kg']:.2f}" if item['price_per_kg'] else "?"
        disc = f"£{item['discounted_price_per_kg']:.2f}" if item.get('discounted_price_per_kg') else "?"
        notes = item.get("tasting_notes", "")[:29]
        print(f"{date:<12} {name:<25} {roaster:<18} {price:>7} {disc:>7} {notes:<30}")

    # Save raw data
    out_path = Path.home() / ".beanz_order_history.json"
    out_path.write_text(json.dumps(all_items, indent=2))
    print(f"\n[Saved to {out_path}]")


if __name__ == "__main__":
    main()