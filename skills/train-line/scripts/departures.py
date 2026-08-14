#!/usr/bin/env python3
"""
UK Train Live Departures — OpenLDBWS (Darwin) via Zeep.

Usage:
    python departures.py <station> [--rows N] [--to DEST_CRS] [--arrivals]
    python departures.py home
    python departures.py lip --to wat
    python departures.py waterloo --arrivals --rows 8

Station can be a CRS code (e.g. LIP) or an alias from stations.json.

When filtering by destination, the script checks calling points to find
trains that stop at the destination (even as an intermediate stop).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from zeep import Client, Settings, xsd

WSDL = "http://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01"
# Load API token from config.json (see config.example.json)
_config_path = Path(__file__).parent.parent / "config.json"
if _config_path.exists():
    with open(_config_path) as _f:
        _cfg = json.load(_f)
    TOKEN = _cfg.get("darwin_api_token", "")
else:
    TOKEN = ""

STATIONS_FILE = Path(__file__).parent.parent / "config" / "stations.json"


def load_aliases():
    try:
        with open(STATIONS_FILE) as f:
            data = json.load(f)
        return data.get("aliases", {})
    except Exception:
        return {}


def resolve_station(station_input: str) -> tuple[str, str]:
    """Return (crs_code, display_name). Accepts CRS code or alias."""
    aliases = load_aliases()
    key = station_input.strip().lower()
    if key in aliases:
        a = aliases[key]
        return a["crs"], a["name"]
    return station_input.strip().upper(), station_input.strip().upper()


def make_client():
    settings = Settings(strict=False)
    client = Client(wsdl=WSDL, settings=settings)
    header = xsd.Element(
        "{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken",
        xsd.ComplexType([
            xsd.Element(
                "{http://thalesgroup.com/RTTI/2013-11-28/Token/types}TokenValue",
                xsd.String()
            ),
        ])
    )
    header_value = header(TokenValue=TOKEN)
    return client, header_value


def get_calling_points(client, header, service_id: str) -> list[dict]:
    """Get calling points for a service. Returns list of {crs, name, st, et}."""
    try:
        details = client.service.GetServiceDetails(serviceID=service_id, _soapheaders=[header])
    except Exception:
        return []

    points = []
    if not details.subsequentCallingPoints:
        return points

    try:
        for cp_group in details.subsequentCallingPoints.callingPointList:
            if hasattr(cp_group, "callingPoint"):
                for cp in cp_group.callingPoint:
                    crs = cp.crs if hasattr(cp, "crs") else ""
                    name = cp.locationName if hasattr(cp, "locationName") else ""
                    st = cp.st if hasattr(cp, "st") else ""
                    et = cp.et if hasattr(cp, "et") else "N/A"
                    points.append({"crs": crs, "name": name, "st": st, "et": et})
    except Exception:
        pass

    return points


def extract_nrcc(msg) -> str:
    """Extract text from an NRCCMessage object."""
    raw = ""
    if hasattr(msg, "__values__") and "_value_1" in msg.__values__:
        raw = msg.__values__["_value_1"]
    elif hasattr(msg, "__values__"):
        for v in msg.__values__.values():
            raw = str(v)
            break
    else:
        raw = str(msg)
    text = re.sub(r"<[^>]+>", "", raw).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > 120:
        text = text[:117] + "..."
    return text


def format_board(res) -> str:
    """Format a StationBoard response into a readable departure board."""
    lines = []
    lines.append(f"🚉 **{res.locationName}** ({res.crs})")
    lines.append("")

    if res.nrccMessages and res.nrccMessages.message:
        for msg in res.nrccMessages.message:
            lines.append(f"⚠️ {extract_nrcc(msg)}")
        lines.append("")

    services = []
    if res.trainServices and res.trainServices.service:
        services = res.trainServices.service
    else:
        lines.append("No services currently running.")
        return "\n".join(lines)

    for svc in services:
        cancelled = svc.isCancelled if hasattr(svc, "isCancelled") else False
        dest = "Unknown"
        if svc.destination and svc.destination.location:
            dest = svc.destination.location[0].locationName

        std = svc.std if hasattr(svc, "std") else "??:??"
        etd = svc.etd if hasattr(svc, "etd") else "N/A"
        plat = svc.platform or "TBC"
        op = svc.operator or "?"

        if cancelled:
            status = "❌ CANCELLED"
            reason = f" ({svc.cancelReason})" if hasattr(svc, "cancelReason") and svc.cancelReason else ""
        elif etd == "On time":
            status = "✅ On time"
            reason = ""
        elif etd == "Delayed":
            status = "⏰ Delayed"
            reason = f" ({svc.delayReason})" if hasattr(svc, "delayReason") and svc.delayReason else ""
        elif etd == "Cancelled":
            status = "❌ Cancelled"
            reason = f" ({svc.cancelReason})" if hasattr(svc, "cancelReason") and svc.cancelReason else ""
        else:
            try:
                sched_min = int(std.split(":")[0]) * 60 + int(std.split(":")[1])
                actual_min = int(etd.split(":")[0]) * 60 + int(etd.split(":")[1])
                diff = actual_min - sched_min
                if diff > 0:
                    status = f"⏰ {diff} min late"
                elif diff < 0:
                    status = f"⚡ {abs(diff)} min early"
                else:
                    status = "✅ On time"
            except Exception:
                status = f"ETA {etd}"
            reason = f" ({svc.delayReason})" if hasattr(svc, "delayReason") and svc.delayReason else ""

        line = f"`{std}` → **{dest}** | Plat {plat} | {status}{reason} | {op}"
        lines.append(line)

    return "\n".join(lines)


def format_board_filtered(client, header, from_crs: str, from_name: str,
                          filter_crs: str, num_rows: int) -> str:
    """Show departures that actually call at filter_crs (checks calling points)."""
    lines = []
    lines.append(f"🚉 **{from_name}** ({from_crs}) → {filter_crs}")
    lines.append("")

    # Get all departures (unfiltered) from origin
    res = client.service.GetDepartureBoard(numRows=num_rows * 3, crs=from_crs, _soapheaders=[header])

    if res.nrccMessages and res.nrccMessages.message:
        for msg in res.nrccMessages.message:
            lines.append(f"⚠️ {extract_nrcc(msg)}")
        lines.append("")

    if not res.trainServices or not res.trainServices.service:
        lines.append("No services currently running.")
        return "\n".join(lines)

    matches = []
    for svc in res.trainServices.service:
        if len(matches) >= num_rows:
            break

        sid = svc.serviceID if hasattr(svc, "serviceID") else ""
        if not sid:
            continue

        points = get_calling_points(client, header, sid)
        lip_point = next((p for p in points if p["crs"] == filter_crs), None)

        if lip_point:
            matches.append({
                "svc": svc,
                "lip_time": lip_point["st"],
                "lip_et": lip_point["et"],
            })

    if not matches:
        lines.append(f"No trains calling at {filter_crs} in the next departures.")
        return "\n".join(lines)

    for m in matches:
        svc = m["svc"]
        dest = "Unknown"
        if svc.destination and svc.destination.location:
            dest = svc.destination.location[0].locationName

        std = svc.std if hasattr(svc, "std") else "??:??"
        etd = svc.etd if hasattr(svc, "etd") else "N/A"
        plat = svc.platform or "TBC"
        op = svc.operator or "?"

        lip_time = m["lip_time"]
        lip_et = m["lip_et"]

        # Overall train status
        if etd == "On time":
            status = "✅ On time"
        elif etd == "Delayed":
            status = "⏰ Delayed"
        elif etd == "Cancelled":
            status = "❌ Cancelled"
        else:
            status = f"ETA {etd}"

        # Liphook arrival status
        if lip_et == "On time":
            lip_status = f"arrives **{lip_time}** ✅"
        elif lip_et == "Delayed":
            lip_status = f"arrives **{lip_time}** ⏰"
        elif lip_et == "Cancelled":
            lip_status = f"arrives **{lip_time}** ❌"
        else:
            lip_status = f"arrives **{lip_time}** (ETA {lip_et})"

        line = f"`{std}` → **{dest}** | Plat {plat} | {status} | {op} | {lip_status}"
        lines.append(line)

    return "\n".join(lines)


def format_arrivals(res) -> str:
    """Format an arrival board response."""
    lines = []
    lines.append(f"🚉 **{res.locationName}** ({res.crs}) — Arrivals")
    lines.append("")

    if res.nrccMessages and res.nrccMessages.message:
        for msg in res.nrccMessages.message:
            lines.append(f"⚠️ {extract_nrcc(msg)}")
        lines.append("")

    services = []
    if res.trainServices and res.trainServices.service:
        services = res.trainServices.service
    else:
        lines.append("No services currently arriving.")
        return "\n".join(lines)

    for svc in services:
        origin = "Unknown"
        if svc.origin and svc.origin.location:
            origin = svc.origin.location[0].locationName

        sta = svc.sta if hasattr(svc, "sta") else "??:??"
        eta = svc.eta if hasattr(svc, "eta") else "N/A"
        plat = svc.platform or "TBC"
        op = svc.operator or "?"

        if eta == "On time":
            status = "✅ On time"
        elif eta == "Delayed":
            status = "⏰ Delayed"
        elif eta == "Cancelled":
            status = "❌ Cancelled"
        else:
            status = f"ETA {eta}"

        lines.append(f"`{sta}` from **{origin}** | Plat {plat} | {status} | {op}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="UK train live departures")
    parser.add_argument("station", help="Station name (alias) or CRS code")
    parser.add_argument("--rows", type=int, default=10, help="Number of services")
    parser.add_argument("--to", dest="filter_crs", help="Filter to destination CRS (checks calling points)")
    parser.add_argument("--arrivals", action="store_true", help="Show arrivals instead")
    args = parser.parse_args()

    crs, name = resolve_station(args.station)
    client, header = make_client()

    if args.arrivals:
        res = client.service.GetArrivalBoard(numRows=args.rows, crs=crs, _soapheaders=[header])
        print(format_arrivals(res))
    elif args.filter_crs:
        dest_crs = args.filter_crs.upper()
        print(format_board_filtered(client, header, crs, name, dest_crs, args.rows))
    else:
        res = client.service.GetDepartureBoard(numRows=args.rows, crs=crs, _soapheaders=[header])
        print(format_board(res))


if __name__ == "__main__":
    main()
