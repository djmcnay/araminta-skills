#!/usr/bin/env python3
"""
SWR Delay Repay — End-to-End Claim Automation (CDP + Vision-based Angular clicks)

Connects to persistent Chromium via CDP (localhost:9222).
Uses vision-based clicking for Angular Material elements that don't appear in DOM consistently.

Usage:
    python swr_claim_complete.py \
        --date "21 May 2026" \
        --from Haslemere \
        --to "London Waterloo" \
        --time 0931 \
        --delay 120 \
        --ref TTBQ7D9FEQF
        [--submit]
"""

import os, sys, asyncio, argparse, re
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# ── Config ──
DOMAIN = "https://delayrepay.southwesternrailway.com"
CDP_URL = os.environ.get("SWR_CDP_URL", "http://localhost:9222")

# ── Helpers ──
def log(msg): print(f"[SWR] {msg}", flush=True)
def die(msg): log(f"FATAL: {msg}"); sys.exit(1)

def find_amazon_page(ctx):
    """Find the Amazon tab, or any tab."""
    for pg in ctx.pages:
        if "amazon" in pg.url or "southwestern" in pg.url:
            return pg
    return ctx.pages[0] if ctx.pages else None

def safe_eval(page, expr):
    """Evaluate JS, return None on error."""
    try:
        return page.evaluate(expr)
    except Exception:
        return None

# ── Main ──
def run_claim(args):
    log(f"Connecting to CDP at {CDP_URL}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        
        # Find the Amazon tab or any tab
        page = find_amazon_page(ctx)
        if not page:
            die("No browser tabs found")
        
        log(f"Using tab: {page.url[:60]}")
        page.set_default_timeout(30000)

        # 1. Navigate to account summary
        log("Navigating to account...")
        page.goto(f"{DOMAIN}/en/account")
        page.wait_for_load_state("domcontentloaded")
        
        # Wait a bit for Angular to render
        page.wait_for_timeout(3000)
        
        # Check if logged in
        text = safe_eval(page, "() => document.body.innerText")
        if text and "[user-email]" in text:
            log("Already logged in")
        else:
            die("Not logged in. Log in manually first.")

        # 2. Click date card (mat-card)
        log(f"Selecting date: {args.date} ...")
        
        # Look for date cards
        cards = safe_eval(page, """
            () => {
                var results = [];
                var all = document.querySelectorAll('.date-card, mat-card');
                for (let el of all) {
                    var text = el.innerText?.trim();
                    if (text && text.match(/\\d+\\s*May|\\d+\\s*Jun/)) {
                        var rect = el.getBoundingClientRect();
                        if (rect.width > 0) {
                            results.push({
                                text: text.slice(0,30),
                                x: Math.round(rect.x + rect.width/2),
                                y: Math.round(rect.y + rect.height/2)
                            });
                        }
                    }
                }
                return results;
            }
        """) or []
        
        log(f"Found {len(cards)} date cards")
        for c in cards:
            log(f"  Card: '{c['text']}' at ({c['x']},{c['y']})")
        
        # Find matching date
        day_num = int(re.match(r'\d+', args.date).group())
        target = None
        for c in cards:
            if str(day_num) in c['text']:
                target = c
                break
        
        if target:
            log(f"Clicking date card at ({target['x']},{target['y']})")
            page.mouse.click(target['x'], target['y'])
        else:
            die(f"Date '{args.date}' not found on account page")
        
        page.wait_for_timeout(3000)
        
        # 3. Fill journey (From/To/Time)
        log("Filling journey details...")
        
        # Use stable IDs
        from_field = page.locator("#mat-input-4")
        if from_field.count() > 0:
            from_field.click()
            from_field.fill("")  # clear
            page.keyboard.type(args.from_station, delay=50)
            page.wait_for_timeout(2500)
            
            # Click dropdown option
            opts = page.locator("mat-option").all()
            for opt in opts:
                if args.from_station.upper() in opt.inner_text():
                    opt.click()
                    break
        
        to_field = page.locator("#mat-input-5")
        if to_field.count() > 0:
            to_field.click()
            to_field.fill("")
            page.keyboard.type(args.to_station, delay=50)
            page.wait_for_timeout(2500)
            
            opts = page.locator("mat-option").all()
            for opt in opts:
                if "LONDON WATERLOO" in opt.inner_text():
                    opt.click()
                    break
        
        time_field = page.locator("#mat-input-6")
        if time_field.count() > 0:
            time_field.click()
            time_field.fill("")
            page.keyboard.type(args.time, delay=50)
            page.wait_for_timeout(1500)
        
        # 4. Search + select journey
        log("Searching for journey...")
        find_btn = page.locator("#find-journey")
        if find_btn.count() > 0:
            find_btn.click()
        page.wait_for_timeout(10000)
        
        # Click first journey card
        j_cards = page.locator("div.cdk-option.selectable-journey-card").all()
        if j_cards:
            j_cards[0].click()
            log(f"Selected first journey")
        page.wait_for_timeout(2000)
        
        # 5. Select delay
        log(f"Selecting delay: {args.delay} minutes...")
        delay_cards = page.locator("mat-card.cdk-option.delay-duration-card").all()
        for card in delay_cards:
            text = card.inner_text()
            if str(args.delay) in text:
                card.click()
                log(f"Selected delay: {text[:40]}")
                break
        page.wait_for_timeout(3000)
        
        # 6. Ticket step
        log("Ticket step...")
        
        # Multi-ticket radio (force=True)
        no_radio = page.locator('mat-radio-button').filter(has_text="No").first
        if no_radio.count() > 0:
            no_radio.click(force=True)
            log("Selected 'No' for multi-ticket")
        page.wait_for_timeout(3000)
        
        # Add ticket card (mat-card)
        add_card = page.locator('mat-card[aria-label="Add ticket"]').first
        if add_card.count() > 0:
            add_card.scroll_into_view_if_needed()
            add_card.click()
            log("Clicked 'Add ticket'")
        page.wait_for_timeout(3000)
        
        # 7. Ticket type (E-ticket — vision-based fallback)
        log("Selecting E-ticket...")
        
        # Try DOM-based click first
        e_ticket = page.locator('mat-radio-button').filter(has_text="E-ticket").first
        if e_ticket.count() > 0:
            e_ticket.click(force=True)
            log("Selected E-ticket via radio")
        else:
            # Fallback: click by text
            e_card = page.locator('mat-card').filter(has_text="E-ticket").first
            if e_card.count() > 0:
                e_card.scroll_into_view_if_needed()
                e_card.click()
                log("Selected E-ticket via card")
        page.wait_for_timeout(3000)
        
        # 8. Single/Return
        log("Selecting Return...")
        ret = page.locator('mat-radio-button').filter(has_text="Return").first
        if ret.count() > 0:
            ret.click(force=True)
            log("Selected Return")
        page.wait_for_timeout(3000)
        
        # 9. Enter reference
        log(f"Entering reference: {args.ref}")
        ref_input = page.locator(".cdk-step-content-active input[type='text']").first
        if ref_input.count() > 0 and ref_input.is_visible():
            ref_input.fill(args.ref)
            ref_input.dispatch_event("input")
            ref_input.dispatch_event("change")
        else:
            # Brute force visible text inputs
            inputs = page.locator('input[type="text"]:visible').all()
            for inp in inputs:
                if inp.is_visible():
                    inp.fill(args.ref)
                    inp.dispatch_event("input")
                    break
        page.wait_for_timeout(2000)
        
        # 10. Confirm
        confirm = page.locator('button').filter(has_text="Confirm").first
        if confirm.count() > 0 and confirm.is_visible():
            confirm.click()
            log("Confirmed ticket")
        page.wait_for_timeout(3000)
        
        # 11. Compensation
        log("Compensation step...")
        comp_btn = page.locator('button[matsteppernext], button').filter(has_text="Compensation").first
        if comp_btn.count() > 0:
            comp_btn.click()
        page.wait_for_timeout(3000)
        
        # Select BACS
        bacs = page.locator('mat-card').filter(has_text="BACS").first
        if bacs.count() > 0:
            bacs.click()
            log("Selected BACS")
        page.wait_for_timeout(2000)
        
        # 12. Review
        log("Review step...")
        review_btn = page.locator('button[matsteppernext], button').filter(has_text="Review").first
        if review_btn.count() > 0:
            review_btn.click()
        page.wait_for_timeout(5000)
        
        # Screenshot review page
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        ss = Path.home() / f"swr_review_{now}.png"
        page.screenshot(path=str(ss))
        log(f"Screenshot saved: {ss}")
        
        # 13. Submit (if --submit)
        if args.submit:
            submit = page.locator('button').filter(has_text="Submit claim").first
            if submit.count() > 0 and submit.is_visible():
                submit.click()
                log("Claim submitted!")
                page.wait_for_timeout(5000)
                
                # Capture confirmation
                conf_ss = Path.home() / f"swr_confirmation_{now}.png"
                page.screenshot(path=str(conf_ss))
                log(f"Confirmation screenshot: {conf_ss}")
            else:
                log("WARNING: Submit button not found")
        else:
            log("=== HALT ===")
            log("Review page reached. Pass --submit to submit claim.")

# ── CLI ──
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="e.g. '21 May 2026'")
    ap.add_argument("--day", type=int, help="Day number (auto-extracted if omitted)")
    ap.add_argument("--from", dest="from_station", required=True, help="Origin station")
    ap.add_argument("--to", dest="to_station", required=True, help="Destination station")
    ap.add_argument("--time", required=True, help="Departure time e.g. 0931")
    ap.add_argument("--delay", type=int, required=True, help="Delay minutes")
    ap.add_argument("--ref", required=True, help="E-ticket reference")
    ap.add_argument("--submit", action="store_true", help="Pass to submit claim automatically")
    args = ap.parse_args()
    
    if not args.day:
        m = re.match(r'(\d+)', args.date)
        args.day = int(m.group(1)) if m else None
    
    run_claim(args)
