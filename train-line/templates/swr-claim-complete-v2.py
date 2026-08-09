#!/usr/bin/env python3
"""
SWR Delay Repay — End-to-End Claim Automation (May 2026, corrected)

Connects to persistent Chromium via CDP (localhost:9222) — already logged in.
Uses stable #mat-input-* selectors, force=True Angular radio clicks, and
keyboard.type() for autocomplete.

Usage:
    python3 swr_claim_complete_v2.py \
        --date "21 May 2026" \
        --from Haslemere \
        --to "London Waterloo" \
        --time 0931 \
        --delay 120 \
        --ref TTBQ7D9FEQF \
        [--submit]

--submit  = proceed past Review and click Submit claim (auto-confirm mode)
            Omit to halt at Review for the user's approval.

Environment: connects to CDP port 9222 (Hermes persistent browser).
No password or cookie file needed.
"""

import sys, asyncio, argparse, re, json
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. See SKILL.md for installation instructions.")
    sys.exit(1)

# ── Config ──
DOMAIN = "https://delayrepay.southwesternrailway.com"
_config_path = Path(__file__).parent.parent / "config.json"
CDP_URL = "http://localhost:9222"
if _config_path.exists():
    with open(_config_path) as _f:
        _cfg = json.load(_f)
    CDP_URL = _cfg.get("cdp_url", CDP_URL)

# ── Helpers ──
def log(msg): print(f"[SWR] {msg}", flush=True)
def die(msg): print(f"[SWR] FATAL: {msg}", file=sys.stderr); sys.exit(1)

async def click_by_text(page, text, wait_ms=2000):
    """Click first visible element with matching text via JS (handles viewport overflow)."""
    found = await page.evaluate("""
        ({txt}) => {
            for (const el of document.querySelectorAll('button, mat-card, a')) {
                if (el.textContent.toLowerCase().includes(txt.toLowerCase()) && el.offsetHeight > 0) {
                    el.click(); return true;
                }
            }
            return false;
        }
    """, text)
    if found:
        await page.wait_for_timeout(wait_ms)
    return found

async def solve_angular_radio(page, label_substring):
    """Click Angular Material mat-radio-button with force=True."""
    loc = page.locator("mat-radio-button").filter(has_text=re.compile(re.escape(label_substring), re.I)).first
    if await loc.count() == 0:
        # Fallback: keyboard on focused wrapper
        card = page.locator("mat-card, div.cdk-option").filter(has_text=re.compile(re.escape(label_substring), re.I)).first
        if await card.count() == 0:
            return False
        await card.scroll_into_view_if_needed()
        await card.focus()
        await page.keyboard.press("Space")
        await page.wait_for_timeout(1000)
        return True
    else:
        await loc.scroll_into_view_if_needed()
        await loc.click(force=True)
        await page.wait_for_timeout(1000)
        return True

async def pick_calendar_day(page, day_number):
    """Open calendar and click numbered day."""
    toggle = page.locator('button.mat-datepicker-toggle-button, button[aria-label*="Open calendar"]').first
    if await toggle.is_visible():
        await toggle.click()
    else:
        await page.locator('#mat-input-0').click()
    await page.wait_for_timeout(1500)
    for btn in await page.locator('button').all():
        if (await btn.inner_text()).strip() == str(day_number):
            await btn.click(); break
    await page.wait_for_timeout(1200)

async def click_ticket_type(page, label):
    """Click a ticket-type card (cdk-option ticket-medium or mat-card)."""
    # First try cdk-option card by visible text
    cards = await page.locator('.cdk-option.ticket-medium').all()
    for c in cards:
        text = await c.inner_text()
        if label.lower() in text.lower():
            rect = await c.evaluate("el => el.getBoundingClientRect()")
            if rect['y'] > 0:
                await page.mouse.click(rect['x'] + rect['width']/2, rect['y'] + rect['height']/2)
                await page.wait_for_timeout(1500)
                return True
    # Fallback: force=True on mat-card
    loc = page.locator('mat-card').filter(has_text=re.compile(re.escape(label), re.I)).first
    if await loc.count() > 0:
        await loc.scroll_into_view_if_needed()
        await loc.click(force=True)
        await page.wait_for_timeout(1500)
        return True
    return False

async def click_duration(page, label):
    """Click an sr-ticket-duration element (Single/Return/Rover etc)."""
    durations = await page.locator('sr-ticket-duration').all()
    for d in durations:
        text = await d.inner_text()
        if label.lower() in text.lower():
            rect = await d.evaluate("el => el.getBoundingClientRect()")
            if rect['y'] > 0:
                await page.mouse.click(rect['x'] + rect['width']/2, rect['y'] + rect['height']/2)
                await page.wait_for_timeout(1500)
                return True
    # Fallback: get_by_text
    loc = page.get_by_text(label, exact=False).first
    if await loc.count() > 0:
        await loc.click(force=True)
        await page.wait_for_timeout(1000)
        return True
    return False

async def click_aui_continue(page, text_substring):
    """Click a button[matsteppernext] by contained text, using JS for viewport-overflow resilience."""
    clicked = await page.evaluate("""
        ({txt}) => {
            for (const b of document.querySelectorAll('button[matsteppernext]')) {
                if (b.textContent.toLowerCase().includes(txt.toLowerCase()) && b.offsetHeight > 0) {
                    b.click(); return true;
                }
            }
            return false;
        }
    """, text_substring)
    if clicked:
        await page.wait_for_timeout(3000)
        return True
    # Fallback: Playwright locator
    loc = page.locator('button[matsteppernext]').filter(has_text=re.compile(re.escape(text_substring), re.I)).first
    if await loc.count() > 0:
        await loc.click(force=True)
        await page.wait_for_timeout(3000)
        return True
    return False

# ── Main ──
async def run_claim(args):
    async with async_playwright() as p:
        log(f"Connecting to CDP at {CDP_URL} ...")
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            die(f"Cannot connect to CDP: {e}. Is Chromium running with --remote-debugging-port=9222?")

        ctx = browser.contexts()[0]
        if not ctx:
            die("No browser context on CDP.")

        page = None
        for pg in ctx.pages:
            url = await pg.url()
            if "delayrepay" in url or "amazon" in url:
                page = pg
                break
        if not page:
            page = await ctx.new_page()

        page.set_default_timeout(30000)

        # 1. Navigate to Account Summary (skip login — already logged in via CDP)
        log("Navigating to account ...")
        await page.goto(f"{DOMAIN}/en/account")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # Check login state
        body_text = await page.locator("body").inner_text()
        if "log in" in body_text.lower() and "email address" in body_text.lower():
            die("Not logged in. Log in manually via VNC first.")

        # 2. Click date from account summary
        log(f"Selecting date: {args.date} ...")
        day_num = args.day or int(re.match(r'(\d+)', args.date).group(1))

        # Try clicking date card (mat-card with date)
        date_clicked = await click_by_text(page, args.date)
        if not date_clicked:
            # Fallback: calendar picker
            await pick_calendar_day(page, day_num)

        await page.wait_for_url("**/make-claim**", timeout=15000)
        await page.wait_for_timeout(1500)
        log("On make-claim page")

        # 3. Journey — use STABLE #mat-input-* IDs, never .nth()
        log("Filling journey ...")

        # From: #mat-input-1
        from_in = page.locator('#mat-input-1')
        await from_in.click()
        await page.keyboard.type(args.from_station, delay=50)
        await page.wait_for_timeout(2500)
        for opt in await page.locator("mat-option").all():
            if args.from_station.upper() in await opt.inner_text():
                await opt.click(); break

        # To: #mat-input-2
        to_in = page.locator('#mat-input-2')
        await to_in.click()
        await page.keyboard.type(args.to_station, delay=50)
        await page.wait_for_timeout(2500)
        for opt in await page.locator("mat-option").all():
            if args.to_station.upper() in await opt.inner_text():
                await opt.click(); break

        # Time: #mat-input-3
        time_in = page.locator('#mat-input-3')
        await time_in.click()
        await page.keyboard.type(args.time, delay=50)
        await page.wait_for_timeout(1500)
        log("Journey filled")

        # 4. Search
        log("Searching ...")
        await page.locator("#find-journey").click()
        await page.wait_for_timeout(10000)

        j = page.locator("div.cdk-option.selectable-journey-card").first
        if await j.is_visible():
            await j.click()
        await page.wait_for_timeout(2000)
        log("Journey selected")

        # 5. Delay selection
        log("Selecting delay ...")
        delay_clicked = False
        cards = page.locator("mat-card.cdk-option.delay-duration-card")
        for i in range(await cards.count()):
            c = cards.nth(i)
            if str(args.delay) in await c.inner_text():
                await c.click(); delay_clicked = True; break
        if not delay_clicked:
            log("WARNING: Could not match delay card. Available delays:")
            for i in range(await cards.count()):
                log(f"  [{i}] {await cards.nth(i).inner_text()}")
        await page.wait_for_timeout(3000)

        # 6. Ticket step
        log("Ticket step ...")
        # 6A. Multiple tickets?  No = single ticket
        multi_ok = await solve_angular_radio(page, "No")
        if not multi_ok:
            log("WARNING: Could not click 'No' on multiple-tickets radio")
        await page.wait_for_timeout(3000)

        # 6B. Add ticket card
        add = page.locator('mat-card[aria-label="Add ticket"]').first
        if await add.count() > 0 and await add.is_visible():
            await add.scroll_into_view_if_needed()
            await add.click()
            log("Clicked Add ticket")
        else:
            log("WARNING: Add ticket card not visible")
        await page.wait_for_timeout(3000)

        # 6C. Ticket type — E-ticket/M-ticket
        log("Selecting E-ticket ...")
        type_ok = await click_ticket_type(page, "E-ticket")
        if not type_ok:
            log("WARNING: Could not select E-ticket type")
        await page.wait_for_timeout(2000)

        # 6D. Duration — Return
        log("Selecting Return ...")
        dur_ok = await click_duration(page, "Return")
        if not dur_ok:
            log("WARNING: Could not select Return")
        await page.wait_for_timeout(2000)

        # 6E. Reference entry
        log(f"Entering reference: {args.ref} ...")
        ref_input = page.locator(".cdk-step-content-active input[type='text']").first
        if await ref_input.is_visible():
            await ref_input.scroll_into_view_if_needed()
            await ref_input.fill(args.ref)
            await ref_input.dispatch_event("input")
            await ref_input.dispatch_event("change")
        else:
            # Brute-force visible text inputs
            for inp in await page.locator('input[type="text"]:visible').all():
                await inp.scroll_into_view_if_needed()
                await inp.fill(args.ref)
                await inp.dispatch_event("input")
                await inp.dispatch_event("change")
                break
        await page.wait_for_timeout(2000)

        # 6F. Confirm ticket
        confirmed = await click_by_text(page, "Confirm", wait_ms=5000)
        if confirmed:
            log("Ticket confirmed")
        else:
            log("WARNING: Confirm button not found")

        # 7. Compensation → BACS
        log("Compensation ...")
        comp_clicked = await click_aui_continue(page, "Compensation")
        if not comp_clicked:
            log("WARNING: Could not navigate to Compensation")
        await page.wait_for_timeout(2000)

        # Click BACS card
        bacs_clicked = await page.evaluate("""
            () => {
                for (const c of document.querySelectorAll('mat-card')) {
                    if (c.textContent.includes('BACS') && c.offsetHeight > 0) { c.click(); return true; }
                }
                return false;
            }
        """)
        if bacs_clicked:
            log("BACS selected")
        await page.wait_for_timeout(2000)

        # 8. Review
        log("Review page ...")
        review_clicked = await click_aui_continue(page, "Review")
        if not review_clicked:
            log("WARNING: Could not navigate to Review")
        await page.wait_for_timeout(5000)

        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        ss_path = Path.home() / f"swr_review_{now}.png"
        await page.screenshot(path=str(ss_path))
        log(f"Screenshot: {ss_path}")

        # 9. Submit (if --submit)
        if args.submit:
            log("--submit passed: clicking Submit claim ...")
            submit_btn = page.locator('button').filter(has_text="Submit claim").first
            if await submit_btn.count() > 0:
                await submit_btn.click()
                await page.wait_for_timeout(10000)

                url = page.url
                if "/claim-confirmation" in url:
                    log("=== CLAIM SUBMITTED ===")
                    text = await page.locator("body").inner_text()
                    ref_match = re.search(r'SWR-\d+-\d+-\d+', text)
                    if ref_match:
                        log(f"Reference: {ref_match.group()}")
                else:
                    log(f"WARNING: After submit, URL is {url}")
            else:
                log("WARNING: Submit button not found")
        else:
            log("=== HALT ===")
            log("Review page reached. Pass --submit to auto-submit, or click manually.")

        await browser.disconnect()

# ── CLI ──
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="Date text, e.g. '21 May 2026'")
    ap.add_argument("--day", type=int, default=None, help="Day number (for calendar fallback)")
    ap.add_argument("--from", dest="from_station", required=True)
    ap.add_argument("--to",   dest="to_station",   required=True)
    ap.add_argument("--time", required=True, help="e.g. 0931")
    ap.add_argument("--delay", type=int, required=True, help="Delay minutes substring")
    ap.add_argument("--ref",  required=True, help="E-ticket reference (e.g. TTBQ7D9FEQF)")
    ap.add_argument("--submit", action="store_true", help="Auto-submit past Review")
    args = ap.parse_args()
    if not args.day:
        m = re.match(r'(\d+)', args.date)
        args.day = int(m.group(1)) if m else None
    asyncio.run(run_claim(args))
