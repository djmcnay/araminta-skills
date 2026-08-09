---
name: nordvpn
description: Control NordVPN on the host machine. Connect, disconnect, and check status. Use for WhatsApp reconnection (avoid Meta IP blocks), geo-located browsing (search from another country), and bypassing UK age-verification. Triggered by "connect VPN", "use VPN", "browse from [country]", "go via VPN", "disconnect VPN".
ownership: collab
version: 1.0.0
author: Minty + the user
license: MIT
metadata:
  hermes:
    tags: [vpn, privacy, nordvpn, network, geo]
---

# NordVPN — Host machine Skill

NordVPN is installed natively on the host machine. All host machine traffic routes through the VPN when connected. This is **separate** from containerized VPN (separate from host), which runs its own isolated NordVPN inside Docker.

**Script:** `~/.hermes/skills/nordvpn/scripts/vpn.py`
**CLI binary:** `/usr/bin/nordvpn`
**Default country:** United Kingdom

---

## Quick Reference

```bash
PYTHON=python3
SKILL=~/.hermes/skills/nordvpn/scripts/vpn.py

$PYTHON $SKILL status
$PYTHON $SKILL connect
$PYTHON $SKILL connect --country United_Kingdom
$PYTHON $SKILL connect --country South_Africa
$PYTHON $SKILL disconnect
$PYTHON $SKILL countries
```

All commands output JSON, making them easy to parse in `execute_code`.

---

## Use Cases

### 1. WhatsApp reconnection
Meta occasionally blocks residential IP addresses associated with bot-like behaviour.
If the WhatsApp bridge fails to reconnect after a period of downtime, try connecting
via VPN before restarting the bridge — a fresh IP may clear the block.

```bash
python3 $SKILL connect --country United_Kingdom
# restart WhatsApp bridge, then:
python3 $SKILL disconnect
```

### 2. Geo-located browsing / search
Connect to a country to get localised search results, prices, or content.

```bash
python3 $SKILL connect --country South_Africa
# do the research / browsing
python3 $SKILL disconnect
```

Common countries: `United_Kingdom`, `South_Africa`, `United_States`, `Germany`,
`France`, `Netherlands`, `Sweden`. See `python3 $SKILL countries` for the full list.

### 3. UK age-verification bypass
UK regulations require ID verification on some over-18 sites. Connecting via a
non-UK server presents a foreign IP and bypasses the prompt. the user is over 18 —
this is legal and appropriate.

```bash
python3 $SKILL connect --country Netherlands   # or any non-UK country
# do the browsing
python3 $SKILL disconnect
```

---

## In execute_code

```python
execute_code("""
import subprocess, json, sys

SKILL = "~/.hermes/skills/nordvpn/scripts/vpn.py"

def vpn(cmd, **kwargs):
    args = ["python3", SKILL, cmd]
    for k, v in kwargs.items():
        args += [f"--{k}", v]
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout)

# Connect to South Africa
result = vpn("connect", country="South_Africa")
print(result["message"])
print("Connected:", result["status"]["connected"])
print("IP:", result["status"]["ip"])
""")
```

---

## Status output

```json
{
  "connected": true,
  "status": "Connected",
  "country": "United Kingdom",
  "city": "London",
  "server": "uk1234.nordvpn.com",
  "ip": "1.2.3.4",
  "technology": "NORDLYNX",
  "uptime": "5 minutes 12 seconds",
  "raw": "..."
}
```

---

## Implementation Notes

### Installation (completed 2026-04-17)

```bash
# Install (repo added automatically by NordVPN install script)
sudo apt-get install -y nordvpn

# Add your account to the nordvpn group (done at install)
sudo usermod -aG nordvpn "$USER"

# Authenticate (same token as containerized VPN (separate from host))
echo "n" | nordvpn login --token <token>   # "n" declines analytics

# Configure
nordvpn set killswitch off      # MUST stay off — see safety note below
nordvpn set autoconnect off     # never auto-connect on host machine startup
nordvpn set analytics off
```

Use your own NordVPN login token from the provider portal. Do not commit token files to the skill repository.

### Group membership note

The `nordvpn` group grants permission to run nordvpn commands without sudo.
The user session must have this group active. The `vpn.py` script uses
`sg nordvpn -c "nordvpn ..."` to ensure the group is active regardless of
whether the current session was started before the group was added.

A full reboot is the clean way to pick up group membership, but `sg` works
without one.

### Safety: killswitch MUST stay disabled on the host

**Do not enable the killswitch on the host machine.**

The killswitch sets the iptables OUTPUT policy to DROP and only allows traffic
through the active VPN tunnel. If the VPN drops for any reason (server restart,
token expiry, network blip), ALL outbound traffic from the host machine is blocked:
- Minty cannot respond on Discord
- WhatsApp bridge disconnects
- Hermes cron jobs fail
- `hermes update` cannot reach GitHub

The `vpn.py connect()` function calls `_ensure_killswitch_off()` before every
connection as a belt-and-suspenders guard.

**containerized VPN (separate from host) is different.** It intentionally runs with killswitch on inside
its container — a torrent IP leak would expose your real address to peers. That
killswitch is isolated to the container's network namespace and cannot affect
the host (confirmed by `test_isolation.py`).

### Relationship to containerized VPN (separate from host)

| | Host NordVPN | containerized VPN (separate from host) NordVPN |
|---|---|---|
| Location | host machine host (system package) | Inside Docker container |
| Killswitch | **Off** | On |
| Affects | All host machine traffic | Only container traffic |
| Purpose | Geo-browsing, WhatsApp, privacy | Torrents, Anna's Archive |
| Starts | On demand via this skill | When containerized VPN (separate from host) container starts |

Both can be active simultaneously without conflict — they use independent tunnels.

---

## Tests

If you maintain local tests for this skill, separate pure unit tests from integration tests that require a live NordVPN daemon. Never run a live connect/disconnect integration test without confirming it is safe to alter the host machine network state.

Unit tests cover: status parsing (connected/disconnected/connecting/error),
connect/disconnect success and failure paths, killswitch guard logic,
countries list parsing.

Integration tests cover: live connect/disconnect to UK and South Africa,
killswitch is confirmed off, countries list populated.
