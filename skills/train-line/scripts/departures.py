#!/usr/bin/env python3
"""UK live departure and arrival boards via National Rail OpenLDBWS."""

import argparse
import json
import re
import sys
from pathlib import Path

WSDL = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01"
REQUEST_TIMEOUT_SECONDS = 10
CONFIG_PATH = Path(__file__).parent.parent / "config.json"
STATIONS_FILE = Path(__file__).parent.parent / "config" / "stations.json"
TOKEN_PLACEHOLDERS = {"", "YOUR_DARWIN_TOKEN_HERE"}


class ConfigurationError(RuntimeError):
    """Raised when local Darwin configuration is missing or invalid."""


def load_token(config_path: Path = CONFIG_PATH) -> str:
    """Load and validate a Darwin token without making a network request."""
    if not config_path.exists():
        raise ConfigurationError(
            f"Darwin API token is not configured. Create {config_path.name} beside "
            f"this script with a darwin_api_token value."
        )
    try:
        with config_path.open(encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read {config_path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ConfigurationError(f"{config_path} must contain a JSON object.")
    token = config.get("darwin_api_token", "")
    if not isinstance(token, str) or token.strip() in TOKEN_PLACEHOLDERS:
        raise ConfigurationError(
            f"{config_path} must contain a non-placeholder darwin_api_token."
        )
    return token.strip()


def load_aliases() -> dict:
    try:
        with STATIONS_FILE.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("aliases", {}) if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_station(station_input: str) -> tuple[str, str]:
    """Return a CRS code and display name for a CRS code or public alias."""
    aliases = load_aliases()
    key = station_input.strip().lower()
    if key in aliases:
        alias = aliases[key]
        return alias["crs"], alias["name"]
    value = station_input.strip().upper()
    return value, value


def make_client(token: str | None = None):
    """Create the Zeep client with bounded WSDL and SOAP operation requests."""
    token = token or load_token()
    from zeep import Client, Settings, xsd
    from zeep.transports import Transport

    transport = Transport(
        timeout=REQUEST_TIMEOUT_SECONDS,
        operation_timeout=REQUEST_TIMEOUT_SECONDS,
    )
    client = Client(
        wsdl=WSDL,
        settings=Settings(strict=False),
        transport=transport,
    )
    header = xsd.Element(
        "{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken",
        xsd.ComplexType(
            [
                xsd.Element(
                    "{http://thalesgroup.com/RTTI/2013-11-28/Token/types}TokenValue",
                    xsd.String(),
                )
            ]
        ),
    )
    return client, header(TokenValue=token)


def get_calling_points(client, header, service_id: str) -> list[dict]:
    """Return subsequent calling points for a service."""
    try:
        details = client.service.GetServiceDetails(
            serviceID=service_id, _soapheaders=[header]
        )
    except Exception:
        return []
    points = []
    if not details.subsequentCallingPoints:
        return points
    try:
        for group in details.subsequentCallingPoints.callingPointList:
            for point in getattr(group, "callingPoint", []):
                points.append(
                    {
                        "crs": getattr(point, "crs", ""),
                        "name": getattr(point, "locationName", ""),
                        "st": getattr(point, "st", ""),
                        "et": getattr(point, "et", "N/A"),
                    }
                )
    except Exception:
        return []
    return points


def extract_nrcc(message) -> str:
    """Extract plain text from an NRCC message object."""
    raw = ""
    values = getattr(message, "__values__", None)
    if values and "_value_1" in values:
        raw = values["_value_1"]
    elif values:
        raw = str(next(iter(values.values())))
    else:
        raw = str(message)
    text = re.sub(r"<[^>]+>", "", raw).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= 120 else text[:117] + "..."


def _messages(response) -> list[str]:
    nrcc = getattr(response, "nrccMessages", None)
    return [extract_nrcc(msg) for msg in getattr(nrcc, "message", [])] if nrcc else []


def _status(scheduled: str, expected: str, service) -> str:
    if getattr(service, "isCancelled", False) or expected == "Cancelled":
        return "CANCELLED"
    if expected == "On time":
        return "On time"
    if expected == "Delayed":
        return "Delayed"
    try:
        scheduled_minutes = int(scheduled[:2]) * 60 + int(scheduled[3:5])
        expected_minutes = int(expected[:2]) * 60 + int(expected[3:5])
        difference = expected_minutes - scheduled_minutes
        if difference > 0:
            return f"{difference} min late"
        if difference < 0:
            return f"{abs(difference)} min early"
        return "On time"
    except (TypeError, ValueError):
        return f"Expected {expected}"


def format_board(response) -> str:
    lines = [f"{response.locationName} ({response.crs})", ""]
    lines.extend(f"WARNING: {message}" for message in _messages(response))
    if _messages(response):
        lines.append("")
    services = getattr(getattr(response, "trainServices", None), "service", [])
    if not services:
        return "\n".join(lines + ["No services currently running."])
    for service in services:
        locations = getattr(getattr(service, "destination", None), "location", [])
        destination = locations[0].locationName if locations else "Unknown"
        scheduled = getattr(service, "std", "??:??")
        expected = getattr(service, "etd", "N/A")
        reason = getattr(service, "cancelReason", None) or getattr(service, "delayReason", None)
        suffix = f" ({reason})" if reason else ""
        lines.append(
            f"{scheduled} to {destination} | Platform {getattr(service, 'platform', None) or 'TBC'} "
            f"| {_status(scheduled, expected, service)}{suffix} | {getattr(service, 'operator', None) or '?'}"
        )
    return "\n".join(lines)


def format_arrivals(response) -> str:
    lines = [f"{response.locationName} ({response.crs}) - Arrivals", ""]
    lines.extend(f"WARNING: {message}" for message in _messages(response))
    if _messages(response):
        lines.append("")
    services = getattr(getattr(response, "trainServices", None), "service", [])
    if not services:
        return "\n".join(lines + ["No services currently arriving."])
    for service in services:
        locations = getattr(getattr(service, "origin", None), "location", [])
        origin = locations[0].locationName if locations else "Unknown"
        scheduled = getattr(service, "sta", "??:??")
        expected = getattr(service, "eta", "N/A")
        lines.append(
            f"{scheduled} from {origin} | Platform {getattr(service, 'platform', None) or 'TBC'} "
            f"| {_status(scheduled, expected, service)} | {getattr(service, 'operator', None) or '?'}"
        )
    return "\n".join(lines)


def format_board_filtered(client, header, from_crs: str, from_name: str, filter_crs: str, rows: int) -> str:
    response = client.service.GetDepartureBoard(
        numRows=rows * 3, crs=from_crs, _soapheaders=[header]
    )
    lines = [f"{from_name} ({from_crs}) to {filter_crs}", ""]
    lines.extend(f"WARNING: {message}" for message in _messages(response))
    matches = []
    for service in getattr(getattr(response, "trainServices", None), "service", []):
        service_id = getattr(service, "serviceID", "")
        point = next(
            (point for point in get_calling_points(client, header, service_id) if point["crs"] == filter_crs),
            None,
        )
        if point:
            matches.append((service, point))
        if len(matches) >= rows:
            break
    if not matches:
        return "\n".join(lines + [f"No trains calling at {filter_crs} in the next departures."])
    for service, point in matches:
        locations = getattr(getattr(service, "destination", None), "location", [])
        destination = locations[0].locationName if locations else "Unknown"
        lines.append(
            f"{getattr(service, 'std', '??:??')} to {destination} | "
            f"Platform {getattr(service, 'platform', None) or 'TBC'} | calls at {filter_crs} {point['st']}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="UK train live departures")
    parser.add_argument("station", help="Public station alias or CRS code")
    parser.add_argument("--rows", type=int, default=10, help="Number of services")
    parser.add_argument("--to", dest="filter_crs", help="Destination CRS calling-point filter")
    parser.add_argument("--arrivals", action="store_true", help="Show arrivals")
    args = parser.parse_args()
    try:
        token = load_token()
        client, header = make_client(token)
        crs, name = resolve_station(args.station)
        if args.arrivals:
            response = client.service.GetArrivalBoard(
                numRows=args.rows, crs=crs, _soapheaders=[header]
            )
            print(format_arrivals(response))
        elif args.filter_crs:
            print(
                format_board_filtered(
                    client, header, crs, name, args.filter_crs.upper(), args.rows
                )
            )
        else:
            response = client.service.GetDepartureBoard(
                numRows=args.rows, crs=crs, _soapheaders=[header]
            )
            print(format_board(response))
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Darwin request failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
