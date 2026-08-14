"""
NordVPN host controller for a host machine.

Wraps the nordvpn CLI installed natively on the host machine. All commands run under the
'nordvpn' group so no sudo is needed. Killswitch is always kept disabled on the
host — it is correct inside containerized VPN (separate from host) (where a traffic leak would expose your
real IP to torrent peers) but catastrophic on the host (it would block Discord,
WhatsApp and other host services if the VPN hiccups).

Typical usage
-------------
    python3 vpn.py status
    python3 vpn.py connect
    python3 vpn.py connect --country United_Kingdom
    python3 vpn.py connect --country South_Africa
    python3 vpn.py disconnect

Or import as a module:
    from vpn import status, connect, disconnect
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict


# ── Internal helper ───────────────────────────────────────────────────────────

def _run(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a nordvpn command. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["sg", "nordvpn", "-c", " ".join(args)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class VpnStatus:
    connected: bool
    status: str          # "Connected" | "Disconnected" | "Connecting" | "unknown"
    country: str | None
    city: str | None
    server: str | None
    ip: str | None
    technology: str | None
    uptime: str | None
    raw: str             # full nordvpn status output

    def to_dict(self) -> dict:
        return asdict(self)


# ── Public API ────────────────────────────────────────────────────────────────

def status() -> VpnStatus:
    """Return the current VPN connection status."""
    rc, out, err = _run(["nordvpn", "status"])

    def _field(label: str) -> str | None:
        m = re.search(rf"^{label}:\s*(.+)$", out, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else None

    status_val = _field("Status") or "unknown"
    connected = status_val.lower() == "connected"

    return VpnStatus(
        connected=connected,
        status=status_val,
        country=_field("Country"),
        city=_field("City"),
        server=_field("Current server"),
        ip=_field("Your new IP"),
        technology=_field("Current technology"),
        uptime=_field("Uptime"),
        raw=out,
    )


def connect(country: str | None = None, city: str | None = None) -> dict:
    """
    Connect to NordVPN.

    Args:
        country: Country name as NordVPN expects it, e.g. "United_Kingdom",
                 "South_Africa", "United_States". None = best available server.
        city:    Optional city within the country, e.g. "London".

    Returns:
        dict with keys: success (bool), message (str), status (VpnStatus)
    """
    _ensure_killswitch_off()

    cmd = ["nordvpn", "connect"]
    if country:
        cmd.append(country)
    if city:
        cmd.append(city)

    rc, out, err = _run(cmd, timeout=60)
    success = rc == 0 and "connected" in out.lower()

    return {
        "success": success,
        "message": out or err,
        "status": status().to_dict(),
    }


def disconnect() -> dict:
    """Disconnect from NordVPN."""
    rc, out, err = _run(["nordvpn", "disconnect"])
    success = rc == 0

    return {
        "success": success,
        "message": out or err,
        "status": status().to_dict(),
    }


def countries() -> list[str]:
    """Return available countries (stripped, sorted)."""
    rc, out, err = _run(["nordvpn", "countries"], timeout=15)
    if rc != 0:
        return []
    # Output is a comma/newline separated list; nordvpn wraps at terminal width
    raw = re.sub(r"[\n\r,]+", " ", out)
    return sorted(c.strip() for c in raw.split() if c.strip())


def _ensure_killswitch_off() -> None:
    """
    Safety guard: always verify killswitch is disabled before connecting.

    On the host machine the killswitch must stay off. If it were enabled and the VPN
    dropped, ALL traffic from the host machine would be blocked — Discord, WhatsApp, every
    Hermes platform — until someone physically intervened.

    containerized VPN (separate from host) runs its own separate NordVPN inside Docker with killswitch on.
    That is correct and intentional. This host install must never have it on.
    """
    rc, out, _ = _run(["nordvpn", "settings"])
    if "Kill Switch: enabled" in out:
        _run(["nordvpn", "set", "killswitch", "off"])


# ── CLI entry point ───────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(
        description="Control NordVPN on the host machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 vpn.py status
  python3 vpn.py connect
  python3 vpn.py connect --country United_Kingdom
  python3 vpn.py connect --country South_Africa
  python3 vpn.py disconnect
  python3 vpn.py countries
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show current VPN status")

    p_conn = sub.add_parser("connect", help="Connect to NordVPN")
    p_conn.add_argument("--country", default=None,
                        help="Country name, e.g. United_Kingdom, South_Africa")
    p_conn.add_argument("--city", default=None, help="Optional city within country")

    sub.add_parser("disconnect", help="Disconnect from NordVPN")
    sub.add_parser("countries", help="List available countries")

    args = parser.parse_args()

    if args.command == "status":
        s = status()
        print(json.dumps(s.to_dict(), indent=2))

    elif args.command == "connect":
        result = connect(country=args.country, city=args.city)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["success"] else 1)

    elif args.command == "disconnect":
        result = disconnect()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["success"] else 1)

    elif args.command == "countries":
        for c in countries():
            print(c)


if __name__ == "__main__":
    _cli()
