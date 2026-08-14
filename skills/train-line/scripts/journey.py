#!/usr/bin/env python3
"""Generate read-only UK rail journey and JourneyCheck links."""

import argparse
import json
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

STATIONS_FILE = Path(__file__).parent.parent / "config" / "stations.json"


def load_stations() -> dict:
    try:
        with STATIONS_FILE.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {"aliases": {}}
    except (OSError, json.JSONDecodeError):
        return {"aliases": {}}


def resolve_station(station_input: str, stations: dict) -> tuple[str, str]:
    key = station_input.strip().lower()
    alias = stations.get("aliases", {}).get(key)
    if alias:
        return alias["crs"].upper(), alias["name"]
    value = station_input.strip().upper()
    return value, value


def build_nationalrail_url(from_crs: str, to_crs: str, date: str | None = None, time: str | None = None) -> str:
    date = date or datetime.now().strftime("%Y-%m-%d")
    time = time or (datetime.now() + timedelta(minutes=5)).strftime("%H:%M")
    query = urllib.parse.urlencode(
        {
            "type": "single",
            "origin": from_crs.upper(),
            "destination": to_crs.upper(),
            "leavingType": "departing",
            "leavingDate": date.replace("-", ""),
            "leavingTime": time.replace(":", ""),
            "adults": 1,
        }
    )
    return f"https://www.nationalrail.co.uk/journey-planner/?{query}"


def build_journeycheck_url(from_crs: str, to_crs: str) -> str:
    query = urllib.parse.urlencode(
        {"from": from_crs.upper(), "to": to_crs.upper()}
    )
    return f"https://www.journeycheck.com/swr/search?{query}"


def print_links(from_crs: str, to_crs: str, date: str, time: str) -> None:
    print(f"Journey: {from_crs} to {to_crs}")
    print(f"Date and time: {date} {time}")
    print("National Rail journey link:")
    print(build_nationalrail_url(from_crs, to_crs, date, time))
    print("SWR JourneyCheck live fallback:")
    print(build_journeycheck_url(from_crs, to_crs))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate read-only UK rail links")
    parser.add_argument("--from", dest="from_station", required=True, help="Origin alias or CRS")
    parser.add_argument("--to", dest="to_station", required=True, help="Destination alias or CRS")
    parser.add_argument("--date", help="Travel date in YYYY-MM-DD format")
    parser.add_argument("--time", help="Departure time in HH:MM format")
    parser.add_argument("--return", dest="return_journey", action="store_true", help="Also generate return links")
    parser.add_argument("--return-time", default="18:00", help="Return departure time")
    args = parser.parse_args()

    stations = load_stations()
    from_crs, _ = resolve_station(args.from_station, stations)
    to_crs, _ = resolve_station(args.to_station, stations)
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    time = args.time or (datetime.now() + timedelta(minutes=5)).strftime("%H:%M")

    print_links(from_crs, to_crs, date, time)
    if args.return_journey:
        print("")
        print_links(to_crs, from_crs, date, args.return_time)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
