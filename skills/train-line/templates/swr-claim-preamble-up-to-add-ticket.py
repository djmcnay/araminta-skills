#!/usr/bin/env python3
"""
Template: SWR Delay Repay — Auto-fill up to "Add ticket", then pause for manual type selection.

This script automates Steps 1–6B (login through clicking "Add ticket" card).
After that, the Angular Material ticket-type radio buttons refuse all programmatic clicks.
The script pauses; the user clicks the E-ticket/M-ticket radio manually via VNC,
then tells the script to continue (or the script can be extended to take over again
after Duration selection, which does respond to click()).

Copy this file, adjust the constants at the top, and run.
"""
import asyncio
from playwright.async_api import async_playwright

# ── CONFIG ── Adjust these for each claim ──
EMAIL       = "[user-email]"
PWD         = "YOUR_PASSWORD_HERE"
TICKET_IMG  = "<your-home>/image_cache/img_f1a1e6dbc200.jpg"
CLAIM_DATE  = "21"          # day of month only (assumes current month/year)
FROM        = "Haslemere"
TO          = "London Waterloo"
TIME        = "0931"
DELAY_TEXT  = "120"        # substring to match in delay card (e.g. "120" for "120 minutes or more")
MULTI_TICKET= False         # True = Yes, False = No

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # 1. LOGIN
        await page.goto(
            "https://delayrepay.southwesternrailway.com/en/login",
            wait_until="networkidle",
            timeout=30000,
        )
        await page.get_by_label("Email Address", exact=True).fill(EMAIL)
        await page.locator('input[type="password"]').first.fill(PWD)
        await page.get_by_role("button", name="Log in").click()
        await page.wait_for_url("**/en/account**", timeout=15000)
        await page.wait_for_timeout(3000)
        print("[1] Logged in")

        # 2. DATE — calendar click
        toggle = page.locator(
            'button.mat-datepicker-toggle-button, button[aria-label="Open calendar"]'
        ).first
        if await toggle.is_visible():
            await toggle.click()
        else:
            await page.locator("#mat-input-0").click()
        await page.wait_for_timeout(1500)
        for btn in await page.locator("button").all():
            if (await btn.inner_text()).strip() == CLAIM_DATE:
                await btn.click()
                break
        await page.wait_for_timeout(1000)
        assert CLAIM_DATE in await page.locator("#mat-input-0").input_value()
        print(f"[2] Date set: {await page.locator('#mat-input-0').input_value()}")

        # 3–5. FROM / TO / TIME
        fin = page.locator("input.mat-autocomplete-trigger").nth(1)
        await fin.click()
        await fin.fill("")
        await page.keyboard.type(FROM, delay=100)
        await page.wait_for_timeout(2500)
        for opt in await page.locator("mat-option").all():
            if FROM.upper() in await opt.inner_text():
                await opt.click()
                break
        await page.wait_for_timeout(500)
        print(f"[3] From: {FROM}")

        tin = page.locator("input.mat-autocomplete-trigger").nth(2)
        await tin.click()
        await tin.fill("")
        await page.keyboard.type(TO, delay=100)
        await page.wait_for_timeout(2500)
        for opt in await page.locator("mat-option").all():
            if "WATERLOO" in (await opt.inner_text()).upper():
                await opt.click()
                break
        await page.wait_for_timeout(500)
        print(f"[4] To: {TO}")

        tim = page.locator('input[aria-label*="Time"]')
        await tim.click()
        await tim.fill("")
        await page.keyboard.type(TIME, delay=100)
        await page.wait_for_timeout(500)
        print(f"[5] Time: {TIME}")

        # 6. SEARCH
        await page.locator("#find-journey").click()
        await page.wait_for_timeout(10000)
        print("[6] Searched")

        # 7. SELECT JOURNEY (fastest = first)
        j = page.locator("div.cdk-option.selectable-journey-card").first
        if await j.is_visible():
            await j.click()
            await page.wait_for_timeout(8000)
        print("[7] Journey selected")

        # 8. DELAY
        cards = page.locator("mat-card.cdk-option.delay-duration-card")
        for i in range(await cards.count()):
            c = cards.nth(i)
            if DELAY_TEXT in await c.inner_text():
                await c.click()
                break
        await page.wait_for_timeout(3000)
        print(f"[8] Delay: {DELAY_TEXT}")

        # 9. MULTI-TICKET RADIO — force=True (only reliable pattern as of May 2026)
        answer = "Yes" if MULTI_TICKET else "No"
        await page.locator("mat-radio-button").filter(has_text=answer).first.click(
            force=True
        )
        await page.wait_for_timeout(4000)
        print(f"[9] Multi-ticket: {answer}")

        # 10. ADD TICKET CARD
        add = page.locator('mat-card[aria-label="Add ticket"]').first
        await add.scroll_into_view_if_needed()
        await add.click()
        await page.wait_for_timeout(3000)
        print("[10] Clicked Add ticket")

        # ── PAUSE HERE ──
        # Angular Material ticket-type radio buttons (E-ticket/M-ticket, Paper, etc.)
        # DO NOT respond to ANY programmatic click pattern tested through May 2026.
        # Open the VNC browser (http://<your-host>:6080/vnc.html) if using headed,
        # or run this script with headless=False and screenshot via vision model.
        # Click the E-ticket/M-ticket radio manually, then continue below.
        print("\n" + "=" * 60)
        print("MANUAL STEP REQUIRED")
        print("Click the E-ticket/M-ticket radio button in the browser,")
        print("then press Enter in this terminal to continue.")
        print("=" * 60 + "\n")
        await page.pause()  # blocks until user closes the browser or script

        # ── BELOW HERE: assumes manual ticket-type selection is done ──
        # 11. DURATION
        await page.get_by_text("Return", exact=True).first.click()
        await page.wait_for_timeout(2000)
        print("[11] Duration: Return")

        # 12. UPLOAD
        await page.locator(
            'input[type="file"][accept*="image/jpeg"]'
        ).first.set_input_files(TICKET_IMG)
        await page.wait_for_timeout(5000)
        print("[12] Image uploaded")

        # 13. CONFIRM
        await page.locator("button").filter(has_text="Confirm").first.click()
        await page.wait_for_timeout(5000)
        print("[13] Ticket confirmed")

        # 14. COMPENSATION (BACS)
        await page.evaluate(
            """() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent.includes('Compensation') && b.offsetHeight > 0) {
                        b.click(); return;
                    }
                }
            }"""
        )
        await page.wait_for_timeout(4000)
        await page.evaluate(
            """() => {
                for (const c of document.querySelectorAll('mat-card')) {
                    if (c.textContent.includes('BACS') && c.offsetHeight > 0) {
                        c.click(); return;
                    }
                }
            }"""
        )
        await page.wait_for_timeout(2000)
        print("[14] Compensation: BACS selected")

        # 15. REVIEW
        await page.evaluate(
            """() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent.toLowerCase().includes('review') && b.offsetHeight > 0) {
                        b.click(); return;
                    }
                }
            }"""
        )
        await page.wait_for_timeout(6000)
        print("[15] Review page reached")
        await page.screenshot(path="/tmp/swr_review.png")

        # 16. SUBMIT
        await page.locator("button").filter(has_text="Submit claim").first.click()
        await page.wait_for_timeout(12000)
        print("[16] Submitted")

        # confirmation
        url = page.url
        print(f"Final URL: {url}")
        if "claim-confirmation" in url:
            print("SUCCESS: claim submitted")
        else:
            print(f"UNEXPECTED URL: {url}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
