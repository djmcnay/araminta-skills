# SWR Claim Preamble Template (May 2026)
# See references/swr-claim-may-2026-playbook.md for full details
# KNOWN BLOCKER: Ticket step radio button click unresolvable in headless mode

import asyncio, re
from playwright.async_api import async_playwright

PWD = "YOUR_PASSWORD_HERE"
TICKET = "/path/to/ticket/image.jpg"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        await page.goto("https://delayrepay.southwesternrailway.com/en/login",
                        wait_until="networkidle", timeout=30000)
        await page.get_by_label("Email Address", exact=True).fill("[user-email]")
        await page.locator('input[type="password"]').first.fill(PWD)
        await page.get_by_role("button", name="Log in").click()
        await page.wait_for_url("**/en/account**", timeout=15000)

        await page.goto("https://delayrepay.southwesternrailway.com/en/make-claim",
                        wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        toggle = page.locator(
            'button.mat-datepicker-toggle-button, button[aria-label="Open calendar"]'
        ).first
        if await toggle.is_visible():
            await toggle.click()
        await page.wait_for_timeout(1500)
        for btn in await page.locator("button").all():
            if (await btn.inner_text()).strip() == "21":
                await btn.click()
                break
        await page.wait_for_timeout(1000)

        fin = page.locator("input.mat-autocomplete-trigger").nth(1)
        await fin.click(); await fin.fill(""); await page.keyboard.type("Haslemere")
        await page.wait_for_timeout(2500)
        for opt in await page.locator("mat-option").all():
            if "HASLEMERE" in await opt.inner_text():
                await opt.click(); break
        await page.wait_for_timeout(1000)

        tin = page.locator("input.mat-autocomplete-trigger").nth(2)
        await tin.click(); await tin.fill(""); await page.keyboard.type("London Waterloo")
        await page.wait_for_timeout(2500)
        for opt in await page.locator("mat-option").all():
            if "LONDON WATERLOO" in await opt.inner_text():
                await opt.click(); break
        await page.wait_for_timeout(1000)

        tim = page.locator('input[aria-label*="Time"]')
        await tim.click(); await tim.fill(""); await page.keyboard.type("0931")
        await page.wait_for_timeout(1000)

        await page.locator("#find-journey").click()
        await page.wait_for_timeout(10000)

        j = page.locator("div.cdk-option.selectable-journey-card").first
        if await j.is_visible():
            await j.click()
        await page.wait_for_timeout(2000)

        cards = page.locator("mat-card.cdk-option.delay-duration-card")
        for i in range(await cards.count()):
            if "120" in await cards.nth(i).inner_text():
                await cards.nth(i).click()
                break
        await page.wait_for_timeout(2000)

        await page.screenshot(path="/tmp/swr_ticket_step.png")
        print("Reached Ticket step. Radio button automation pending.")

        await browser.close()

asyncio.run(main())
