#!/usr/bin/env node
/**
 * Amazon Returns CLI — Playwright-based return automation
 * Usage: node amazon-returns-cli.js "Via Crema tamper" "incompatible or not useful" <cookie-file>
 *
 * Steps (updated 2026-04-29 from live run):
 *   1. Authenticate via imported cookies
 *   2. Search order history by product name (URL-based: /your-orders/search)
 *   3. Click "View order details" link, then "Return items"
 *   4. Deselect unneeded items, ensure target is checked
 *   5. Select reason from AUI dropdown → sync native select + dispatch events
 *   6. Fill comments textarea (required for most reasons, esp. "Incompatible")
 *   7. Click "Continue" (span-based button, id=orc-items-section-continue-button-announce)
 *   8. Check "Yes, please issue my refund" checkbox on refund page
 *   9. Click "Continue" on refund page (id=resolutions-section-continue-button-announce)
 *  10. Select Post Office radio on carrier/drop-off page
 *  11. Click "Choose drop-off location" button → modal → enter postcode → search
 *  12. Click first "Dropoff here" button in results
 *  13. Click "CONFIRM YOUR RETURN" button
 *  14. Capture reference number from final page
 *  15. Screenshot final state
 */

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

// ─── Config ──────────────────────────────────────────────────────────
const AMAZON_DOMAIN = "https://www.amazon.co.uk";
const HEADLESS = process.env.AMAZON_RETURNS_HEADLESS === "1";
const TIMEOUT_MS = 30_000;
const DEFAULT_POSTCODE = process.env.AMAZON_RETURNS_POSTCODE || "GU30 7QN";

// ─── Helpers ─────────────────────────────────────────────────────────
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function log(...args) {
  console.log("[amazon-returns]", ...args);
}

function die(msg) {
  console.error("[amazon-returns] FATAL:", msg);
  process.exit(1);
}

// Load cookies from file (JSON array, Netscape, or header string)
function loadCookies(filepath) {
  const raw = fs.readFileSync(filepath, "utf-8").trim();
  try {
    const arr = JSON.parse(raw);
    return arr.map((c) => ({
      name: c.name,
      value: c.value,
      domain: c.domain || ".amazon.co.uk",
      path: c.path || "/",
      expires: c.expirationDate || -1,
      httpOnly: c.httpOnly || false,
      secure: c.secure !== false,
      sameSite: c.sameSite || "Lax",
    }));
  } catch {
    // Netscape format
    const lines = raw.split("\n").filter((l) => !l.startsWith("#") && l.trim());
    return lines.map((l) => {
      const [domain, , path, secure, expires, name, ...val] = l.split("\t");
      return {
        name,
        value: val.join("\t"),
        domain: domain.replace(/^\./, ""),
        path,
        expires: parseInt(expires) || -1,
        httpOnly: domain.startsWith("#HttpOnly_"),
        secure: secure === "TRUE",
        sameSite: "Lax",
      };
    });
  }
}

// ─── Main ────────────────────────────────────────────────────────────
async function main() {
  const [rawQuery, reasonArg, cookieFile] = process.argv.slice(2);
  if (!rawQuery) die('Usage: node amazon-returns-cli.js "<product>" "[reason]" <cookies.json>');

  const reasonText = reasonArg || "no reason given";
  const reasonLower = reasonText.toLowerCase();

  log("Launching browser ...");
  const browser = await chromium.launch({
    headless: HEADLESS,
    args: ["--disable-blink-features=AutomationControlled"],
  });

  try {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await ctx.newPage();
    page.setDefaultTimeout(TIMEOUT_MS);

    // ── 1. Seed cookies ──────────────────────────────────────────────────
    if (cookieFile) {
      if (!fs.existsSync(cookieFile)) die(`cookie file not found: ${cookieFile}`);
      const cookies = loadCookies(cookieFile);
      await ctx.addCookies(cookies);
      log(`Loaded ${cookies.length} cookies`);
    }

    // ── 2. Search order history by product name ──────────────────────────
    // Amazon has a dedicated "Search all orders" input on the orders page.
    // The simplest path: search by navigating to the search URL.
    const searchTerm = encodeURIComponent(rawQuery);
    const searchUrl = `${AMAZON_DOMAIN}/gp/your-account/order-history?orderFilter=last30&search=${searchTerm}`;
    log("Searching orders:", rawQuery);
    await page.goto(searchUrl);
    await page.waitForLoadState("domcontentloaded");
    await sleep(2000);

    // Check if we see the product in results
    const bodyText = await page.locator("body").innerText();
    if (!bodyText.toLowerCase().includes(rawQuery.toLowerCase())) {
      // Fall back: use the /your-orders/search endpoint
      const searchOrderUrl = `${AMAZON_DOMAIN}/your-orders/search?opt=ab&search=${searchTerm}`;
      await page.goto(searchOrderUrl);
      await page.waitForLoadState("domcontentloaded");
      await sleep(2000);
    }

    // ── 3. Click "View order details" then "Return items" ──────────────
    // Look for the order detail link
    const detailLink = page.locator('a[href*="order-details"]').first();
    if (!(await detailLink.isVisible().catch(() => false))) {
      die("Could not find order details link. May need manual login.");
    }
    await detailLink.click();
    await sleep(2000);

    // On the order detail page, find "Return items" link
    const returnLink = page.locator('a[href*="/spr/returns/cart"]').first();
    if (!(await returnLink.isVisible().catch(() => false))) {
      die("Could not find 'Return items' link on order detail page.");
    }
    const returnHref = await returnLink.getAttribute("href");
    const returnUrl = returnHref.startsWith("http") ? returnHref : `${AMAZON_DOMAIN}${returnHref}`;
    log("Opening return cart:", returnUrl);
    await page.goto(returnUrl);
    await page.waitForLoadState("domcontentloaded");
    await sleep(2000);

    // ── 4. Handle item checkboxes ──────────────────────────────────────
    // There may be multiple returnable items. Our target item should be checked;
    // others should be unchecked. By default Amazon checks the first item.
    //
    // Strategy: find all item-selection checkboxes, identify which one is the
    // correct item (by surrounding text), ensure it's checked and others are not.
    const itemCheckboxes = page.locator('css=[id$="-self_serviceable-orc-item-selection-checkbox"]');
    const cbCount = await itemCheckboxes.count();
    log(`Found ${cbCount} returnable item(s)`);

    if (cbCount === 0) {
      die("No item checkboxes found on return cart page.");
    }

    // Identify our target: the one whose parent region mentions the search term
    let targetIndex = 0;
    for (let i = 0; i < cbCount; i++) {
      const cb = itemCheckboxes.nth(i);
      // Get the containing order card text
      const parentText = await cb.evaluate((el) => {
        const row = el.closest('[class*="order"], [class*="item"], .a-box');
        return (row || el.parentElement).innerText.substring(0, 200);
      });
      if (parentText.toLowerCase().includes(rawQuery.toLowerCase())) {
        targetIndex = i;
        break;
      }
    }

    // Ensure target is checked, others are not
    for (let i = 0; i < cbCount; i++) {
      const cb = itemCheckboxes.nth(i);
      const isChecked = await cb.isChecked();
      const shouldBeChecked = (i === targetIndex);

      if (isChecked !== shouldBeChecked) {
        await cb.scrollIntoViewIfNeeded();
        await cb.click();
        await cb.evaluate((el) => {
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        });
        log(`Item ${i}: ${shouldBeChecked ? "checked" : "unchecked"}`);
      }
    }
    await sleep(1000);

    // ── 5. Select reason ──────────────────────────────────────────────
    // Amazon renders: a hidden native <select> + a visible AUI wrapper.
    // The native select ID pattern: <itemId>-self_serviceable-...-native-dropdown
    const nativeSelect = page.locator('css=[id$="-native-dropdown"]').first();
    const nativeVisible = await nativeSelect.isVisible().catch(() => true);

    // Open the AUI popover
    const wrap = nativeSelect.locator('xpath=../span[contains(@class,"a-button-dropdown")]');
    await wrap.scrollIntoViewIfNeeded();
    await wrap.click();
    await sleep(800);

    // Get all dropdown option texts
    const opts = await page.locator("div.a-popover-inner li a").allTextContents();
    log("Reason dropdown options:", opts.slice(0, 10));

    // Match by substring
    let picked = opts.find((o) => o.toLowerCase().includes(reasonLower)) ||
                 opts.find((o) => o === "No reason given") ||
                 opts[0];

    if (!picked) die("No dropdown options found for reason selection.");

    // Click the AUI option
    const optEl = page.locator("div.a-popover-inner li a", { hasText: picked }).first();
    await optEl.click();
    log("AUI reason selected:", picked);
    await sleep(500);

    // Sync the native select
    const optionValues = await nativeSelect.locator("option").evaluateAll((opts) =>
      opts.map((o, i) => ({ index: i, value: o.value, text: o.textContent.trim() }))
    );
    const matched = optionValues.find((o) => o.text === picked) || optionValues[0];
    if (matched) {
      log("Syncing native option: index", matched.index, "value:", matched.value);
      await nativeSelect.evaluate((el, val) => {
        const nativeSetter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
        if (nativeSetter?.set) {
          nativeSetter.set.call(el, val);
        } else {
          el.value = val;
        }
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        el.dispatchEvent(new CustomEvent("aui:change", { bubbles: true }));
      }, matched.value);
    }
    await sleep(1500);

    // ── 6. Fill comments textarea ─────────────────────────────────────
    // Amazon shows a conditionally-visible textarea based on the selected reason.
    // For "Incompatible or not useful for intended purpose", the textarea ID is:
    //   <itemId>-self_serviceable-...-RO_CR-NOT_COMPATIBLE-AC_REQUIRED_WHAT_IS_WRONG
    //
    // After selecting the reason, the matching textarea becomes visible.
    // We need to find the currently-visible required textarea for this item.

    const visibleTextareas = page.locator('textarea:visible').filter({
      has: page.locator('.. >> text=required|Required|describe|Describe', { hasText: true }),
    });

    const textareaCount = await visibleTextareas.count();

    if (textareaCount > 0) {
      const ta = visibleTextareas.first();
      const commentText = `Tamper is 54mm which is the wrong size for Sage Barista Express portafilter. Does not fit the machine.`;
      await ta.scrollIntoViewIfNeeded();
      await ta.fill(commentText);
      // Dispatch events so Amazon validation picks up the filled text
      await ta.evaluate((el) => {
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      });
      log(`Filled comments (${commentText.length} chars)`);
    } else {
      // For reasons like "No reason given", the textarea may be optional/hidden.
      // This is fine — no comment needed.
      log("No visible required textarea — comments not needed for this reason");
    }
    await sleep(1200);

    // ── 7. Click Continue on return cart page ─────────────────────────
    // The Continue button is a span with id="orc-items-section-continue-button-announce"
    // inside a clickable container. We click the span itself (which Amazon handles).

    let cartContinued = false;
    for (let attempt = 0; attempt < 3; attempt++) {
      const continueSpans = page.locator('css=[id$="items-section-continue-button-announce"]');
      const spanCount = await continueSpans.count();
      if (spanCount === 0) {
        log("Continue span not found yet, waiting...");
        await sleep(1500);
        continue;
      }

      const btn = continueSpans.first();
      // Check if disabled via parent a-button
      const isDisabled = await btn.evaluate((el) => {
        const gp = el.closest("span.a-button");
        return gp?.classList.contains("a-button-disabled");
      });

      if (isDisabled) {
        log("Cart Continue still disabled (attempt", attempt + 1, "/3)");
        await sleep(2000);
        continue;
      }

      await btn.scrollIntoViewIfNeeded();
      await btn.click();
      log("Cart-page Continue clicked");
      cartContinued = true;
      break;
    }

    if (!cartContinued) {
      log("WARNING: Could not click Continue on cart page.");
      await page.screenshot({ path: "/tmp/amazon-returns-continue-stuck.png", fullPage: true });
    }
    await sleep(3000);

    // ── 8. Refund page: check "Yes, please issue my refund" ───────────
    // The refund page has: radio buttons for refund method + a checkbox
    //   "Yes, please issue my refund on my Amazon account."
    // The checkbox ID pattern: <itemId>-acknowledgementId

    const refundBody = await page.locator("body").innerText();
    const onRefundPage = /how can we make it right|refund/i.test(refundBody);

    if (onRefundPage) {
      log("Refund page detected");

      // Amazon defaults to Amazon balance — stick with it.
      // Find and check the acknowledgement checkbox
      const ackCheckbox = page.locator('css=[id$="-acknowledgementId"]').first();
      const ackVisible = await ackCheckbox.isVisible().catch(() => false);

      if (ackVisible) {
        if (!(await ackCheckbox.isChecked())) {
          await ackCheckbox.scrollIntoViewIfNeeded();
          await ackCheckbox.click();
          await ackCheckbox.evaluate((el) => {
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
          });
          log("'Yes, please issue my refund' checkbox ticked");
        } else {
          log("Refund acknowledgement already checked");
        }
        await sleep(1500);
      } else {
        log("No refund acknowledgement checkbox found — may not be required");
      }

      // ── 9. Click Continue on refund page ──────────────────────────
      let refundContinued = false;
      for (let attempt = 0; attempt < 3; attempt++) {
        const refBtn = page.locator('css=[id="resolutions-section-continue-button-announce"]').first();
        const rv = await refBtn.isVisible().catch(() => false);

        if (!rv) {
          log("Refund Continue not visible, waiting...");
          await sleep(1500);
          continue;
        }

        const isDisabled = await refBtn.evaluate((el) => {
          const gp = el.closest("span.a-button");
          return gp?.classList.contains("a-button-disabled");
        });

        if (isDisabled) {
          log("Refund Continue still disabled (attempt", attempt + 1, "/3)");
          await sleep(2000);
          continue;
        }

        await refBtn.scrollIntoViewIfNeeded();
        await refBtn.click();
        log("Refund-page Continue clicked");
        refundContinued = true;
        break;
      }

      if (!refundContinued) {
        log("WARNING: Could not proceed past refund page.");
        await page.screenshot({ path: "/tmp/amazon-returns-refund-stuck.png", fullPage: true });
      }
      await sleep(3000);
    }

    // ── 10. Carrier / drop-off page ─────────────────────────────────
    const carrierBody = await page.locator("body").innerText();
    const onCarrierPage = /how would you like to return|drop.off|carrier/i.test(carrierBody);

    if (onCarrierPage) {
      log("Carrier / drop-off page detected");

      // List available carriers
      const carrierRadios = page.locator('css=input[type="radio"]:visible');
      const crc = await carrierRadios.count();
      log(`Found ${crc} carrier option(s)`);

      // Prefer Post Office
      let carrierSelected = false;

      for (let i = 0; i < crc; i++) {
        const r = carrierRadios.nth(i);
        const labelText = await r.evaluate((el) => {
          const parent = el.closest("label, div.a-radio, span.a-radio-label, div.a-column");
          return parent?.innerText?.substring(0, 80) || "";
        });

        if (/post office/i.test(labelText)) {
          await r.scrollIntoViewIfNeeded();
          await r.evaluate((el) => {
            el.click();
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
          });
          log("Selected Post Office drop-off");
          carrierSelected = true;
          await sleep(1500);
          break;
        }
      }

      if (!carrierSelected) {
        // Fall back to Evri
        for (let i = 0; i < crc; i++) {
          const r = carrierRadios.nth(i);
          const labelText = await r.evaluate((el) => {
            const parent = el.closest("label, div.a-radio, span.a-radio-label, div.a-column");
            return parent?.innerText?.substring(0, 80) || "";
          });
          if (/evri/i.test(labelText)) {
            await r.scrollIntoViewIfNeeded();
            await r.evaluate((el) => {
              el.click();
              el.dispatchEvent(new Event("input", { bubbles: true }));
              el.dispatchEvent(new Event("change", { bubbles: true }));
            });
            log("Selected Evri drop-off");
            carrierSelected = true;
            await sleep(1500);
            break;
          }
        }
      }

      if (!carrierSelected && crc > 0) {
        // Surface to user — no Post Office or Evri available
        log("WARNING: Neither Post Office nor Evri available. Options:");
        for (let i = 0; i < crc; i++) {
          const r = carrierRadios.nth(i);
          const labelText = await r.evaluate((el) => {
            const parent = el.closest("label, div.a-radio, span.a-radio-label, div.a-column");
            return parent?.innerText?.substring(0, 80) || "";
          });
          log("  ", i, ":", labelText);
        }
        die("No preferred carrier (Post Office or Evri) available. Cannot proceed automatically.");
      }

      // ── 11. Choose drop-off location (Post Office only) ──────────
      // If Post Office was selected, a "Choose drop-off location" button appears.
      const chooseBtn = page.locator('css=[id$="-widget-trigger"]').first();
      const chooseVisible = await chooseBtn.isVisible().catch(() => false);

      if (chooseVisible) {
        log("Opening drop-off location chooser ...");
        await chooseBtn.scrollIntoViewIfNeeded();
        await chooseBtn.click();
        await sleep(2000);

        // Wait for modal with postcode input
        const postcodeInput = page.locator('input[placeholder*="postcode"], input[placeholder*="address"]').first();
        const piVisible = await postcodeInput.isVisible().catch(() => false);

        if (piVisible) {
          await postcodeInput.fill(DEFAULT_POSTCODE);
          log("Entered postcode:", DEFAULT_POSTCODE);

          // Click search
          const searchBtn = page.locator('button[aria-label="Search"], button:has-text("Search")').first();
          if (await searchBtn.isVisible().catch(() => false)) {
            await searchBtn.click();
          } else {
            // Press Enter
            await postcodeInput.press("Enter");
          }
          await sleep(3000);

          // Click first "Dropoff here" button in results
          const dropoffBtn = page.locator('button:has-text("Dropoff here")').first();
          if (await dropoffBtn.isVisible().catch(() => false)) {
            // Get the location name for logging
            const locationEl = dropoffBtn.locator('xpath=ancestor::li//h3').first();
            const locationName = await locationEl.innerText().catch(() => "unknown");
            await dropoffBtn.click();
            log("Selected drop-off location:", locationName);
          } else {
            die("No Dropoff here buttons found in location results.");
          }
          await sleep(2000);
        } else {
          log("WARNING: Postcode input not found in modal. May need manual intervention.");
        }
      }

      // ── 12. Click CONFIRM YOUR RETURN ────────────────────────────
      let confirmed = false;
      for (let attempt = 0; attempt < 3; attempt++) {
        const confirmBtn = page.locator('button:has-text("Confirm your return"), input[value*="confirm" i]').first();
        const cv = await confirmBtn.isVisible().catch(() => false);

        if (!cv) {
          log("Confirm button not visible, waiting...");
          await sleep(1500);
          continue;
        }

        const isDisabled = await confirmBtn.evaluate((el) => {
          return el.disabled || el.classList.contains("a-button-disabled");
        });

        if (isDisabled) {
          log("Confirm button disabled (attempt", attempt + 1, "/3)");
          await sleep(2000);
          continue;
        }

        await confirmBtn.scrollIntoViewIfNeeded();
        await confirmBtn.click();
        log("'Confirm your return' clicked");
        confirmed = true;
        break;
      }

      if (!confirmed) {
        log("WARNING: Could not click Confirm.");
        await page.screenshot({ path: "/tmp/amazon-returns-confirm-stuck.png", fullPage: true });
      }
      await sleep(3000);
    }

    // ── 13. Capture final confirmation / reference ──────────────────
    const finalText = await page.locator("body").innerText();
    log("Final page snippet:", finalText.substring(0, 500));

    const refMatch =
      finalText.match(/[A-Z0-9]{10,}/) ||
      finalText.match(/reference[:\s]*([A-Za-z0-9-]+)/i) ||
      finalText.match(/number[:\s]*([A-Za-z0-9-]+)/i);

    if (refMatch) log("Confirmation / reference number:", refMatch[1] || refMatch[0]);

    await page.screenshot({ path: "/tmp/amazon-returns-final.png", fullPage: true });
    log("Final screenshot: /tmp/amazon-returns-final.png");

    // ── 14. Done ────────────────────────────────────────────────────
    log("Done. Pausing 60s (Ctrl+C to exit).");
    await sleep(60_000);

  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
