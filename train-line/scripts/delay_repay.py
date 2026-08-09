#!/usr/bin/env python3
"""
Delay Repay Evidence Store — saves QR code screenshots for later claim filing.

Usage:
    python delay_repay.py store <image_path> [--train-id TRAIN_ID] [--notes NOTES]
    python delay_repay.py list
    python delay_repay.py info <store_id>

Images are copied to data/delay_repay/ with an index.json manifest.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

DATA_DIR = Path(__file__).parent.parent / "data" / "delay_repay"
INDEX_FILE = DATA_DIR / "index.json"


def load_index() -> dict:
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {"entries": []}


def save_index(index: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


def store_image(image_path: str, train_id: str = "", notes: str = "") -> str:
    """Copy image to delay_repay store and record in index."""
    src = Path(image_path)
    if not src.exists():
        print(f"ERROR: File not found: {image_path}")
        sys.exit(1)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    store_id = uuid4().hex[:8]
    timestamp = datetime.now().isoformat()
    
    ext = src.suffix.lower() or ".png"
    dest_name = f"{store_id}_{timestamp[:10]}{ext}"
    dest = DATA_DIR / dest_name
    
    shutil.copy2(src, dest)
    
    entry = {
        "id": store_id,
        "stored_at": timestamp,
        "original_path": str(src),
        "stored_path": str(dest),
        "filename": dest_name,
        "train_id": train_id,
        "notes": notes,
        "size_bytes": dest.stat().st_size,
        "delay_repay_filed": False,
        "claim_reference": "",
    }
    
    index = load_index()
    index["entries"].append(entry)
    save_index(index)
    
    return store_id


def list_entries():
    index = load_index()
    if not index["entries"]:
        print("No delay repay evidence stored yet.")
        return
    
    print(f"📋 Delay Repay Evidence ({len(index['entries'])} entries)")
    print("=" * 60)
    
    for e in index["entries"]:
        filed = "✅ FILED" if e.get("delay_repay_filed") else "⏳ PENDING"
        ref = f" | Ref: {e['claim_reference']}" if e.get("claim_reference") else ""
        train = f" | Train: {e['train_id']}" if e.get("train_id") else ""
        print(f"  [{e['id']}] {e['stored_at'][:16]} | {filed}{train}{ref}")
        if e.get("notes"):
            print(f"    Notes: {e['notes']}")


def mark_filed(store_id: str, claim_ref: str = ""):
    index = load_index()
    for e in index["entries"]:
        if e["id"] == store_id:
            e["delay_repay_filed"] = True
            e["claim_reference"] = claim_ref
            save_index(index)
            print(f"✅ Marked {store_id} as filed" + (f" (ref: {claim_ref})" if claim_ref else ""))
            return
    print(f"ERROR: Entry {store_id} not found")
    sys.exit(1)


def get_entry(store_id: str) -> dict | None:
    index = load_index()
    for e in index["entries"]:
        if e["id"] == store_id:
            return e
    return None


def main():
    parser = argparse.ArgumentParser(description="Delay Repay evidence store")
    sub = parser.add_subparsers(dest="command")

    # store
    p_store = sub.add_parser("store", help="Store a screenshot")
    p_store.add_argument("image_path", help="Path to the screenshot/image")
    p_store.add_argument("--train-id", default="", help="Train service ID or route info")
    p_store.add_argument("--notes", default="", help="Additional notes")

    # list
    sub.add_parser("list", help="List stored evidence")

    # mark-filed
    p_filed = sub.add_parser("mark-filed", help="Mark entry as filed with Delay Repay")
    p_filed.add_argument("store_id", help="Entry ID")
    p_filed.add_argument("--ref", default="", help="Claim reference number")

    args = parser.parse_args()

    if args.command == "store":
        sid = store_image(args.image_path, args.train_id, args.notes)
        print(f"📸 Stored: {sid}")
        print(f"   Location: {DATA_DIR}")
    elif args.command == "list":
        list_entries()
    elif args.command == "mark-filed":
        mark_filed(args.store_id, args.ref)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
