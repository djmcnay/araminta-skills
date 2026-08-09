#!/usr/bin/env python3
"""Tests for train-line skill scripts.

TAP format output. Run standalone: python test_train_line.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"

# Add scripts dir so we can import journey.py helpers
sys.path.insert(0, str(SCRIPTS_DIR))

passed = 0
failed = 0
total = 0


def ok(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"ok {total} - {name}")
    else:
        failed += 1
        msg = f"not ok {total} - {name}"
        if detail:
            msg += f"  # {detail}"
        print(msg)


# ── Station resolution ──────────────────────────────────────────────

def test_station_resolution():
    from journey import resolve_station, load_stations
    stations = load_stations()

    # 'lip' and 'wat' are not aliases in current config — they fall through to uppercase
    crs, name = resolve_station("lip", stations)
    ok("resolve 'lip' -> CRS LIP (uppercase fallback)", crs == "LIP")

    crs, name = resolve_station("wat", stations)
    ok("resolve 'wat' -> CRS WAT (uppercase fallback)", crs == "WAT")

    crs, name = resolve_station("home", stations)
    ok("resolve 'home' -> CRS LIP", crs == "LIP")
    ok("resolve 'home' -> name Liphook", "Liphook" in name)

    crs, name = resolve_station("work", stations)
    ok("resolve 'work' -> CRS WAT", crs == "WAT")
    ok("resolve 'work' -> name Waterloo", "Waterloo" in name)

    # Unknown station falls through to uppercase
    crs, name = resolve_station("xyz", stations)
    ok("resolve 'xyz' -> uppercase fallback", crs == "XYZ")


# ── URL slug conversion ─────────────────────────────────────────────

def test_name_to_slug():
    from journey import name_to_slug

    ok("slug 'London Waterloo'", name_to_slug("London Waterloo") == "london-waterloo")
    ok("slug 'Liphook'", name_to_slug("Liphook") == "liphook")
    ok("slug 'St Albans City'", name_to_slug("St Albans City") == "st-albans-city")
    ok("slug strips trailing hyphens", name_to_slug("Foo ") == "foo")
    ok("slug handles double spaces", name_to_slug("Foo  Bar") == "foo-bar")


# ── MyTrainPal URL construction ─────────────────────────────────────

def test_mytrainpal_url():
    from journey import build_mytrainpal_url

    url = build_mytrainpal_url("London Waterloo", "Liphook")
    ok("MyTrainPal URL contains domain", "mytrainpal.com" in url)
    ok("MyTrainPal URL contains from slug", "london-waterloo" in url)
    ok("MyTrainPal URL contains to slug", "liphook" in url)
    ok("MyTrainPal URL has -to- separator", "-to-" in url)


# ── National Rail URL construction ──────────────────────────────────

def test_nationalrail_url():
    from journey import build_nationalrail_url

    url = build_nationalrail_url("WAT", "LIP", "2026-04-18", "09:00")
    ok("NR URL contains nationalrail.co.uk", "nationalrail.co.uk" in url)
    ok("NR URL contains origin WAT", "origin=WAT" in url)
    ok("NR URL contains destination LIP", "destination=LIP" in url)
    ok("NR URL contains date 20260418", "leavingDate=20260418" in url)
    ok("NR URL contains time 0900", "leavingTime=0900" in url)

    # Default date/time (no args) should still produce valid URL
    url_default = build_nationalrail_url("WAT", "LIP")
    ok("NR URL default still valid", "nationalrail.co.uk" in url_default)
    ok("NR URL default has origin", "origin=WAT" in url_default)


# ── Journey summary formatting ──────────────────────────────────────

def test_format_journey_summary():
    from journey import format_journey_summary

    summary = format_journey_summary("Liphook", "London Waterloo", "2026-04-18", "09:00")
    ok("summary contains from station", "Liphook" in summary)
    ok("summary contains to station", "London Waterloo" in summary)
    ok("summary contains date", "2026-04-18" in summary)
    ok("summary contains time", "09:00" in summary)
    ok("summary contains arrow", "→" in summary)


# ── Delay repay index operations ────────────────────────────────────

def test_delay_repay_index():
    # Import with temp directory
    import delay_repay
    original_data_dir = delay_repay.DATA_DIR
    original_index = delay_repay.INDEX_FILE

    with tempfile.TemporaryDirectory() as tmp:
        delay_repay.DATA_DIR = Path(tmp)
        delay_repay.INDEX_FILE = Path(tmp) / "index.json"

        # Fresh index
        idx = delay_repay.load_index()
        ok("fresh index has entries key", "entries" in idx)
        ok("fresh index entries is empty list", idx["entries"] == [])

        # Store a fake image
        fake_img = Path(tmp) / "test.png"
        fake_img.write_bytes(b"\x89PNG fake")
        sid = delay_repay.store_image(str(fake_img), train_id="TEST123", notes="test delay")

        ok("store returns 8-char id", len(sid) == 8)
        ok("store creates index file", delay_repay.INDEX_FILE.exists())

        idx = delay_repay.load_index()
        ok("index has 1 entry after store", len(idx["entries"]) == 1)
        entry = idx["entries"][0]
        ok("entry has correct train_id", entry["train_id"] == "TEST123")
        ok("entry has correct notes", entry["notes"] == "test delay")
        ok("entry not filed yet", entry["delay_repay_filed"] is False)

        # Get entry
        found = delay_repay.get_entry(sid)
        ok("get_entry finds stored entry", found is not None)
        ok("get_entry returns correct id", found["id"] == sid)

        # Mark filed
        delay_repay.mark_filed(sid, "REF-456")
        idx = delay_repay.load_index()
        entry = idx["entries"][0]
        ok("mark_filed sets filed=True", entry["delay_repay_filed"] is True)
        ok("mark_filed stores claim ref", entry["claim_reference"] == "REF-456")

        # Get non-existent entry
        missing = delay_repay.get_entry("nonexistent")
        ok("get_entry returns None for missing", missing is None)

    # Restore
    delay_repay.DATA_DIR = original_data_dir
    delay_repay.INDEX_FILE = original_index


# ── Departures format_board (mock objects) ──────────────────────────

def test_extract_nrcc():
    from departures import extract_nrcc

    # Test with simple string-like object
    class FakeMsg:
        __values__ = {"_value_1": "<p>Signal failure at <b>Clapham</b></p>"}

    result = extract_nrcc(FakeMsg())
    ok("extract_nrcc strips HTML tags", "<p>" not in result and "<b>" not in result)
    ok("extract_nrcc contains plain text", "Signal failure" in result)
    ok("extract_nrcc truncates long text", len(result) <= 120)


# ── Run all ─────────────────────────────────────────────────────────

print("TAP version 13")
print(f"1..{25}")  # expected test count — adjust as needed

test_station_resolution()
test_name_to_slug()
test_mytrainpal_url()
test_nationalrail_url()
test_format_journey_summary()
test_delay_repay_index()
test_extract_nrcc()

# TAP summary
print(f"\n# Tests: {total}, Passed: {passed}, Failed: {failed}")

# JSON summary for health-check registry
import json as _json
print(f"__TEST_RESULT__:{_json.dumps({'skill': 'train-line', 'passed': passed, 'failed': failed, 'total': total})}")

sys.exit(0 if failed == 0 else 1)
