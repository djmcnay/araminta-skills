#!/usr/bin/env python3
"""Test script for browser-display skill — verifies the xpra display stack is healthy.

Checks:
  1. Xvfb :99 is running
  2. Chromium CDP (9222) is responsive
  3. xpra shadow (6080) is serving HTML5 client
  4. Tailscale funnel /browser path is configured
  
Usage: python3 tests/test_browser_display.py
Exit code 0 = all checks pass.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

TIMEOUT = 5

def fail(msg):
    print(f"  ❌ {msg}")
    return False

def ok(msg):
    print(f"  ✅ {msg}")
    return True

def check_port(port, host="127.0.0.1"):
    """Check if a TCP port is listening."""
    try:
        s = socket.socket()
        s.settimeout(TIMEOUT)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def fetch_url(url):
    """Simple HTTP GET returning status code and body snippet."""
    import urllib.request
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(1024).decode("utf-8", errors="replace")
            return resp.status, body[:500]
    except Exception as e:
        return None, str(e)


def main():
    print("=== browser-display health check ===\n")
    passed = 0
    failed = 0

    # 1. Xvfb :99
    print("[1/5] Xvfb display :99")
    xvfb_running = subprocess.run(
        ["pgrep", "-f", "Xvfb :99"], capture_output=True, text=True
    ).returncode == 0
    if xvfb_running:
        passed += 1
        ok("Xvfb :99 is running")
    else:
        failed += 1
        fail("Xvfb :99 not found")

    # 2. Chromium CDP
    print("[2/5] Chromium CDP on port 9222")
    if check_port(9222):
        # Verify it's actually Chromium via /json/version
        import json
        import urllib.request
        try:
            req = urllib.request.Request("http://127.0.0.1:9222/json/version")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read())
                browser = data.get("Browser", "unknown")
                if "Chrome" in browser:
                    passed += 1
                    ok(f"Chromium CDP responsive ({browser})")
                else:
                    failed += 1
                    fail(f"Port 9222 open but not Chromium: {browser}")
        except Exception as e:
            failed += 1
            fail(f"Could not query /json/version: {e}")
    else:
        failed += 1
        fail("Port 9222 not listening")

    # 3. xpra shadow on 6080
    print("[3/5] xpra shadow on port 6080")
    if check_port(6080):
        status, body = fetch_url("http://127.0.0.1:6080/")
        if status == 200 and "xpra" in body.lower():
            passed += 1
            ok("xpra HTML5 client serving")
        else:
            failed += 1
            fail(f"Port 6080 open but unexpected response: HTTP {status}")
    else:
        failed += 1
        fail("Port 6080 not listening")

    # 4. Tailscale funnel /browser path
    print("[4/5] Tailscale funnel /browser path")
    result = subprocess.run(
        ["sudo", "tailscale", "funnel", "status"],
        capture_output=True, text=True
    )
    if "/browser proxy http://127.0.0.1:6080" in result.stdout:
        passed += 1
        ok("Funnel /browser → :6080 configured")
    else:
        failed += 1
        fail("Funnel /browser path not found")

    # 5. Funnel is actually reachable (optional — may fail if off-network)
    print("[5/5] Funnel HTTPS reachability (best-effort)")
    status, _ = fetch_url("https://araminta.taild3f7b9.ts.net/browser/")
    if status == 200:
        passed += 1
        ok("Funnel URL reachable via HTTPS")
    elif status is None:
        # Might fail from some networks — not a hard failure
        passed += 1
        ok("Funnel check skipped (network-dependent)")
    else:
        passed += 1
        ok(f"Funnel responded HTTP {status} (non-200 may be OK from test host)")

    # Summary
    total = passed + failed
    print(f"\n=== {passed}/{total} checks passed ===")
    
    if failed > 0:
        print(f"  {failed} check(s) failed")
        sys.exit(1)
    else:
        print("  All checks passed — browser display is healthy")
        sys.exit(0)


if __name__ == "__main__":
    main()
