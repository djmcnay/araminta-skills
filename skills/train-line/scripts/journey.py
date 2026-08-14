#!/usr/bin/env python3
"""
UK Train Journey Planner — MyTrainPal links + National Rail cross-validation.

Usage:
    python journey.py --from lip --to wat
    python journey.py --from "london euston" --to lip --date 2026-04-15 --time 09:00
    python journey.py --from lip --to wat --validate   # also checks National Rail
    python journey.py --from lip --to wat --price      # scrape price from MyTrainPal

Outputs MyTrainPal journey URL and optionally National Rail comparison.
"""

import argparse
import json
import re
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

STATIONS_FILE = Path(__file__).parent.parent / "config" / "stations.json"


def load_stations():
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"aliases": {}, "favourites": []}


def resolve_station(station_input: str, stations_data: dict) -> tuple[str, str]:
    aliases = stations_data.get("aliases", {})
    key = station_input.strip().lower()
    if key in aliases:
        a = aliases[key]
        return a["crs"], a["name"]
    return station_input.strip().upper(), station_input.strip().title()


def name_to_slug(name: str) -> str:
    """Convert station name to MyTrainPal URL slug: 'London Waterloo' -> 'london-waterloo'."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def build_mytrainpal_url(from_name: str, to_name: str) -> str:
    """Build a MyTrainPal journey page URL.
    
    MyTrainPal URL format:
      https://www.mytrainpal.com/train-journey/london-waterloo-to-isleworth
    """
    from_slug = name_to_slug(from_name)
    to_slug = name_to_slug(to_name)
    return f"https://www.mytrainpal.com/train-journey/{from_slug}-to-{to_slug}"


def build_nationalrail_url(from_crs: str, to_crs: str, date: str = None, time: str = None) -> str:
    """Build a National Rail journey planner URL for cross-validation."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    if not time:
        time = (datetime.now() + timedelta(minutes=5)).strftime("%H:%M")
    
    date_formatted = date.replace("-", "")
    time_formatted = time.replace(":", "")
    
    return (
        f"https://www.nationalrail.co.uk/journey-planner/"
        f"?type=single&origin={from_crs}&destination={to_crs}"
        f"&leavingType=departing&leavingDate={date_formatted}&leavingTime={time_formatted}"
        f"&adults=1"
    )


def scrape_mytrainpal_price(from_name: str, to_name: str) -> str | None:
    """Scrape ticket price from MyTrainPal journey page using Camoufox.
    
    Returns price string like '£7.00' or None if scraping fails.
    """
    import requests
    
    url = build_mytrainpal_url(from_name, to_name)
    camoufox = "http://localhost:9377"
    user_id = f"araminta-train-{datetime.now().strftime('%H%M%S')}"
    
    try:
        # Create tab
        r = requests.post(f"{camoufox}/tabs", json={
            "userId": user_id,
            "sessionKey": "price-scout"
        }, timeout=15)
        tab = r.json().get("tabId")
        if not tab:
            return None
        
        # Navigate to MyTrainPal journey page
        requests.post(f"{camoufox}/tabs/{tab}/navigate", json={
            "userId": user_id,
            "url": url
        }, timeout=30)
        import time as _time
        _time.sleep(5)
        
        # Get snapshot and look for price
        r = requests.get(f"{camoufox}/tabs/{tab}/snapshot", params={"userId": user_id}, timeout=30)
        snap = r.json().get("snapshot", "")
        
        # Look for price pattern in heading: "From £7.00" or "From £12.34"
        price_match = re.search(r'(?:From\s+)?£(\d+\.\d{2})', snap)
        
        # Also look for timetable rows with depart times
        schedule = []
        for line in snap.split('\n'):
            if re.search(r'\d{2}:\d{2}.*(?:Direct|\d+m)', line):
                schedule.append(line.strip())
        
        # Close tab
        requests.delete(f"{camoufox}/tabs/{tab}", params={"userId": user_id}, timeout=10)
        
        if price_match:
            return f"£{price_match.group(1)}"
        return None
        
    except Exception:
        return None


def scrape_mytrainpal_schedule(from_name: str, to_name: str) -> list[dict]:
    """Get timetable from MyTrainPal journey page. Returns list of {dep, arr, duration, operator}."""
    import requests
    
    url = build_mytrainpal_url(from_name, to_name)
    camoufox = "http://localhost:9377"
    user_id = f"araminta-sched-{datetime.now().strftime('%H%M%S')}"
    
    try:
        r = requests.post(f"{camoufox}/tabs", json={
            "userId": user_id,
            "sessionKey": "schedule-scout"
        }, timeout=15)
        tab = r.json().get("tabId")
        if not tab:
            return []
        
        requests.post(f"{camoufox}/tabs/{tab}/navigate", json={
            "userId": user_id,
            "url": url
        }, timeout=30)
        import time as _time
        _time.sleep(5)
        
        r = requests.get(f"{camoufox}/tabs/{tab}/snapshot", params={"userId": user_id}, timeout=30)
        snap = r.json().get("snapshot", "")
        
        requests.delete(f"{camoufox}/tabs/{tab}", params={"userId": user_id}, timeout=10)
        
        # Parse timetable rows: "HH:MM Station HH:MM Station Duration Direct Operator"
        trains = []
        for line in snap.split('\n'):
            # Match row pattern like: "22:22 London Waterloo 35m, Direct 22:57 Isleworth South Western Railway"
            m = re.search(r'(\d{2}:\d{2})\s+\w+.*?(\d+m),?\s*(Direct|\d+m)?\s*(\d{2}:\d{2})\s+\w+.*?(South Western Railway|Greater Anglia|Southern|GWR|Thameslink)', line)
            if m:
                trains.append({
                    "dep": m.group(1),
                    "duration": m.group(2),
                    "arr": m.group(4),
                    "operator": m.group(5),
                })
        
        return trains[:6]  # Return up to 6 upcoming trains
        
    except Exception:
        return []


def format_journey_summary(from_name: str, to_name: str, date: str, time: str) -> str:
    lines = []
    lines.append(f"🚂 **Journey: {from_name} → {to_name}**")
    lines.append(f"📅 {date} | ⏰ departing from {time}")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="UK train journey planner")
    parser.add_argument("--from", dest="from_station", required=True, help="Origin station (alias or CRS)")
    parser.add_argument("--to", dest="to_station", required=True, help="Destination station (alias or CRS)")
    parser.add_argument("--date", help="Travel date (YYYY-MM-DD), default: today")
    parser.add_argument("--time", help="Departure time (HH:MM), default: now+5min")
    parser.add_argument("--validate", action="store_true", help="Also show National Rail URL")
    parser.add_argument("--return", dest="return_journey", action="store_true", help="Plan return journey too")
    parser.add_argument("--return-time", dest="return_time", default="18:00", help="Return departure time (HH:MM), default: 18:00")
    parser.add_argument("--price", action="store_true", help="Scrape price from MyTrainPal via Camoufox")
    args = parser.parse_args()

    stations = load_stations()
    from_crs, from_name = resolve_station(args.from_station, stations)
    to_crs, to_name = resolve_station(args.to_station, stations)

    date = args.date or datetime.now().strftime("%Y-%m-%d")
    time = args.time or (datetime.now() + timedelta(minutes=5)).strftime("%H:%M")

    print(format_journey_summary(from_name, to_name, date, time))

    # MyTrainPal link (replaces dead Trainline links)
    mtp_url = build_mytrainpal_url(from_name, to_name)
    print(f"🔗 **Train tickets & timetable**:")
    print(f"<{mtp_url}>")
    print("")

    # Price scraping
    if args.price:
        price = scrape_mytrainpal_price(from_name, to_name)
        if price:
            print(f"💷 **Single from {price}**")
        else:
            print("💷 Price: check link above (scrape failed)")
        print("")

    if args.validate:
        nr_url = build_nationalrail_url(from_crs, to_crs, date, time)
        print(f"🔗 **National Rail cross-check**:")
        print(f"<{nr_url}>")
        print("")

    if args.return_journey:
        print("---")
        ret_time = args.return_time
        print(format_journey_summary(to_name, from_name, date, ret_time))
        mtp_url_ret = build_mytrainpal_url(to_name, from_name)
        print(f"🔗 **Return tickets & timetable**:")
        print(f"<{mtp_url_ret}>")
        if args.validate:
            nr_url_ret = build_nationalrail_url(to_crs, from_crs, date, ret_time)
            print(f"🔗 **National Rail return cross-check**:")
            print(f"<{nr_url_ret}>")


if __name__ == "__main__":
    main()
