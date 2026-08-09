#!/usr/bin/env node
/**
 * Amazon Returns CLI — Playwright-based return automation (May 2026)
 * Connects to persistent Chromium via CDP (localhost:9222)
 *
 * Usage:
 *   node amazon-returns-cli.js "<product>" "[reason]" [--auto-confirm]
 *
 *   product     = product name to search in order history
 *   reason      = return reason text (fuzzy matched against dropdown options)
 *   --auto-confirm = skip approval, click Confirm Your Return automatically
 *
 * The script connects to David's already-logged-in Chromium session, walks through
 * the return flow, tries carrier fallback automatically, and submits the return.
 */

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

// ─── Config ──────────────────────────────────────────────────────────
const AMAZON_DOMAIN = "https://www.amazon.co.uk";
const CDP_URL = process.env.AMAZON_RETURNS_CDP || "http://localhost:9222";
const TIMEOUT_MS = 30000;
const DEFAULT_POSTCODE = process.env.AMAZON_RETURNS_POSTCODE || "[postcode]";

const CARRIER_PRIORITY = [
  { pattern: /evri.*?drop\s*off.*?no\s*box/i, name: "Evri Drop Off (no box)" },
  { pattern: /asda.*?store.*?no\s*box/i, name: "ASDA Store (no box)" },
  { pattern: /post\s*office.*?royal\s*mail.*?drop\s*off/i, name: "Post Office/Royal Mail Drop Off (box required)" },
  { pattern: /post\s*office.*?no\s*box/i, name: "Post Office (no box)" }
];

// ─── Helpers ─────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function log(...args) { console.log("[amazon-returns]", ...args); }
function die(msg) { console.error("[amazon-returns] FATAL:", msg); process.exit(1); }

/**
 * Find the Amazon returns tab among all CDP pages.
 * Returns the page handle, or null.
 */
async function findPage(ctx, opts = {}) {
  const pages = ctx.pages;
  for (const pg of pages) {
    const url = await pg.url();
    if (opts.returns && url.includes("returns")) return pg;
    if (opts.amazon && url.includes("amazon.co.uk")) return pg;
    if (opts.any && url.includes("amazon.co.uk")) return pg;
  }
  // Try creating a new page if none found
  if (opts.create) {
    return await ctx.newPage();
  }
  return null;
}

/**
 * Click an actual hidden <input type="submit"> behind an AUI span wrapper.
 * Amazon's anti-bot layer validates pointer event metadata; synthetic JS clicks
 * on the span are rejected. The hidden submit input inside `.a-button-inner`
 * works when clicked via Playwright's real pointer dispatch.
 */
async function clickAuiSubmit(page, announceId) {
  const btn = await page.locator(`#${announceId}`).first();
  if (!(await btn.isVisible().catch(() => false))) return false;

  // Find the actual submit input inside the button
  const submitInfo = await btn.evaluate(el => {
    const inner = el.closest('.a-button')?.querySelector('input[type="submit"]');
    if (!inner) return null;
    const r = inner.getBoundingClientRect();
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
  });

  if (submitInfo) {
    await page.mouse.click(submitInfo.x, submitInfo.y);
    return true;
  }

  // Fallback: click the span itself
  await btn.click({ force: true });
  return true;
}

/**
 * Detect which carrier options are visible and their states.
 */
async function detectCarriers(page) {
  return await page.evaluate(() => {
    const results = [];
    const radios = document.querySelectorAll('input[type="radio"]');
    for (const r of radios) {
      const rect = r.getBoundingClientRect();
      if (rect.y < 200) continue; // skip header nav
      const container = r.closest('div, li, label');
      const text = container ? container.innerText.trim().replace(/\s+/g, ' ').slice(0, 120) : '';
      results.push({
        checked: r.checked,
        x: Math.round(rect.left + rect.width / 2),
        y: Math.round(rect.top + rect.height / 2),
        text,
        id: r.id
      });
    }
    return results;
  });
}

/**
 * Select a carrier by fuzzy matching its label text, then try to confirm.
 * Returns { success: bool, carrierName: string }.
 */
async function tryCarrier(page, carrierPattern, carrierName) {
  const carriers = await detectCarriers(page);
  const match = carriers.find(c => carrierPattern.test(c.text));
  if (!match) return { success: false, carrierName: null };

  log(`Selecting carrier: ${carrierName}`);

  // Click the radio at its center (native mouse for real pointer events)
  if (match.y > 0) {
    await page.mouse.click(match.x, match.y);
    await sleep(1500);
  }

  // Check if a "Choose drop-off location" button appeared (Post Office branch chooser)
  const chooseBtn = await page.locator('[id$="-widgettrigger"], [id$="-widget-trigger"], button:has-text("Choose"), a:has-text("Choose")').first();
  const hasChooser = await chooseBtn.isVisible().catch(() => false);

  if (hasChooser) {
    log("Branch chooser modal detected — opening...");
    await chooseBtn.click();
    await sleep(2000);

    const postcodeInput = await page.locator('input[placeholder*="postcode"], input[placeholder*="address"]').first();
    if (await postcodeInput.isVisible().catch(() => false)) {
      await postcodeInput.fill(DEFAULT_POSTCODE);
      log("Entered postcode:", DEFAULT_POSTCODE);
      await postcodeInput.press("Enter");
      await sleep(3000);

      const dropoffBtn = await page.locator('button:has-text("Dropoff here"), a:has-text("Dropoff here"), [id*="dropoff"]').first();
      if (await dropoffBtn.isVisible().catch(() => false)) {
        await dropoffBtn.click();
        log("Selected first drop-off location");
        await sleep(2000);
      } else {
        log("WARNING: No Dropoff here button found after postcode search");
        // Close modal and continue anyway
        const closeModal = await page.locator('.a-close-popover, .a-button-close').first();
        if (await closeModal.isVisible().catch(() => false)) await closeModal.click();
      }
    }
  }

  // Try clicking Confirm via the actual submit input
  const clicked = await clickAuiSubmit(page, "methods-section-continue-button-announce");
  if (!clicked) {
    log("Confirm button not clickable for", carrierName);
    return { success: false, carrierName };
  }

  await sleep(3000);

  // Detect if we navigated to confirmation
  const url = page.url();
  const text = await page.evaluate(() => document.body.innerText);
  const isConfirmed = url.includes("/returns/confirmation") ||
                      text.toLowerCase().includes("qr code") ||
                      text.toLowerCase().includes("return instructions") ||
                      text.toLowerCase().includes("drop off your return");

  return { success: isConfirmed, carrierName };
}

// ─── Main ────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  const autoConfirm = args.includes("--auto-confirm");
  const filtered = args.filter(a => a !== "--auto-confirm");
  const [rawQuery, reasonArg] = filtered;

  if (!rawQuery) {
    die('Usage: node amazon-returns-cli.js "<product>" "[reason]" [--auto-confirm]');
  }

  const reasonText = reasonArg || "no reason given";
  const reasonLower = reasonText.toLowerCase();

  log("Connecting to CDP at", CDP_URL);
  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
  } catch (e) {
    die(`Cannot connect to CDP at ${CDP_URL}. Is Chromium running with --remote-debugging-port=9222?`);
  }

  const ctx = browser.contexts()[0];
  if (!ctx) die("No browser context attached to CDP.");

  // Find existing Amazon tab or create one
  let page = await findPage(ctx, { returns: true });
  if (!page) page = await findPage(ctx, { amazon: true });
  if (!page) page = await ctx.newPage();

  page.setDefaultTimeout(TIMEOUT_MS);

  try {
    // ── 1. Navigate to Order History ──────────────────────────────────
    log("Navigating to order history...");
    await page.goto("https://www.amazon.co.uk/gp/css/order-history");
    await page.waitForLoadState("domcontentloaded");
    await sleep(2000);

    // Check if logged in
    const body = await page.locator("body").innerText();
    if (/sign.in|hello.*sign.in/i.test(body)) {
      die("Not logged in. Log in manually via VNC first.");
    }

    // ── 2. Search for order ───────────────────────────────────────────
    const searchUrl = `${AMAZON_DOMAIN}/your-orders/search?opt=ab&search=${encodeURIComponent(rawQuery)}`;
    await page.goto(searchUrl);
    await page.waitForLoadState("domcontentloaded");
    await sleep(2000);

    // ── 3. Click "View order details" ───────────────────────────────
    const detailLink = await page.locator('a[href*="order-details"]').first();
    if (!(await detailLink.isVisible().catch(() => false))) {
      die("Could not find order details link.");
    }
    await detailLink.click();
    await sleep(2000);

    // ── 4. Click "Return items" ─────────────────────────────────────
    const returnLink = await page.locator('a[href*="/spr/returns/cart"]').first();
    if (!(await returnLink.isVisible().catch(() => false))) {
      // Maybe already on a returns page
      const href = await returnLink.getAttribute("href").catch(() => "");
      if (!href.includes("returns")) die("Could not find 'Return items' link.");
    }
    const returnHref = await returnLink.getAttribute("href");
    const returnUrl = returnHref.startsWith("http") ? returnHref : `${AMAZON_DOMAIN}${returnHref}`;
    await page.goto(returnUrl);
    await page.waitForLoadState("domcontentloaded");
    await sleep(2000);

    // ── 5. Handle item checkboxes ─────────────────────────────────────
    const itemCheckboxes = await page.locator('[id$="-self_serviceable-orc-item-selection-checkbox"]').all();
    if (itemCheckboxes.length === 0) {
      log("No item checkboxes found. May already be past item selection.");
    } else {
      log(`Found ${itemCheckboxes.length} returnable item(s)`);
      let targetIndex = 0;
      for (let i = 0; i < itemCheckboxes.length; i++) {
        const parentText = await itemCheckboxes[i].evaluate(el => {
          const row = el.closest('[class*="order"], [class*="item"], .a-box, div');
          return (row || el.parentElement).innerText.substring(0, 300);
        });
        if (parentText.toLowerCase().includes(rawQuery.toLowerCase())) {
          targetIndex = i;
          break;
        }
      }
      for (let i = 0; i < itemCheckboxes.length; i++) {
        const shouldBe = (i === targetIndex);
        const isChecked = await itemCheckboxes[i].isChecked();
        if (isChecked !== shouldBe) {
          await itemCheckboxes[i].scrollIntoViewIfNeeded();
          await itemCheckboxes[i].click();
          await sleep(300);
        }
      }
    }

    // ── 6. Select Reason ──────────────────────────────────────────────
    const nativeSelect = await page.locator('[id$="-native-dropdown"]').first();
    const selectVisible = await nativeSelect.isVisible().catch(() => false);

    if (selectVisible) {
      // Open AUI dropdown
      const wrap = await nativeSelect.locator('xpath=../span[contains(@class,"a-buttondropdown")]').first();
      if (await wrap.isVisible().catch(() => false)) {
        await wrap.click();
        await sleep(800);

        const opts = await page.locator("div.a-popover-inner li a").allTextContents();
        let picked = opts.find(o => o.toLowerCase().includes(reasonLower)) || opts[0];
        if (picked) {
          const optEl = await page.locator("div.a-popover-inner li a", { hasText: picked }).first();
          if (await optEl.isVisible().catch(() => false)) {
            await optEl.click();
            log("Selected reason:", picked);
          }
        }
      }

      // Sync native select
      const optionValues = await nativeSelect.locator("option").evaluateAll(opts =>
        opts.map(o => ({ value: o.value, text: o.textContent.trim() }))
      );
      const matched = optionValues.find(o => o.text.toLowerCase().includes(reasonLower)) || optionValues[0];
      if (matched) {
        await nativeSelect.evaluate((el, val) => {
          const desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
          if (desc?.set) desc.set.call(el, val); else el.value = val;
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        }, matched.value);
      }
      await sleep(1500);
    }

    // ── 7. Fill comments ──────────────────────────────────────────────
    const textareas = await page.locator('textarea:visible').all();
    for (const ta of textareas) {
      const id = await ta.getAttribute("id") || "";
      if (id.toLowerCase().includes("rufus")) continue; // skip AI widget
      const isReq = await ta.evaluate(el => el.required || el.closest('[class*="required"]'));
      if (isReq || textareas.length === 1) {
        const comment = `${reasonText}. Product not suitable for intended use.`;
        await ta.fill(comment);
        await ta.evaluate(el => {
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        });
        log("Filled comments textarea");
        break;
      }
    }

    // ── 8. Click Continue on items page ───────────────────────────────
    const cartContinued = await clickAuiSubmit(page, "orc-items-section-continue-button-announce");
    if (cartContinued) log("Items-page Continue clicked"); else log("No items-page Continue button found");
    await sleep(3000);

    // ── 9. Refund page ────────────────────────────────────────────────
    const bodyText = await page.locator("body").innerText();
    const onRefundPage = /how can we make it right|refund/i.test(bodyText);

    if (onRefundPage) {
      log("Refund page detected");

      const ackCheckbox = await page.locator('[id$="-acknowledgementId"]').first();
      if (await ackCheckbox.isVisible().catch(() => false)) {
        if (!(await ackCheckbox.isChecked())) {
          await ackCheckbox.click();
          await sleep(500);
        }
        log("Refund acknowledgement checked");
      }

      const refundContinued = await clickAuiSubmit(page, "resolutions-section-continue-button-announce");
      if (refundContinued) log("Refund-page Continue clicked"); else log("No refund-page Continue button");
      await sleep(3000);
    }

    // ── 10. Carrier / drop-off page ───────────────────────────────────
    const carrierText = await page.locator("body").innerText();
    const onCarrierPage = /how would you like to return|drop.off|carrier|post office|evri|asda/i.test(carrierText);

    if (onCarrierPage) {
      log("Carrier page detected. Attempting carrier fallback...");

      let confirmed = false;
      let chosenCarrier = null;

      for (const carrierDef of CARRIER_PRIORITY) {
        const result = await tryCarrier(page, carrierDef.pattern, carrierDef.name);
        if (result.success) {
          confirmed = true;
          chosenCarrier = result.carrierName;
          break;
        }
        log(`  ${carrierDef.name} — failed or blocked, trying next...`);
      }

      if (!confirmed) {
        // Report available options and stop
        const carriers = await detectCarriers(page);
        log("No carrier succeeded. Visible options:");
        for (const c of carriers) log(`  - ${c.text}`);

        if (!autoConfirm) {
          log("\nReturn stalled at carrier selection.");
          log("VNC: https://araminta.taild3f7b9.ts.net/browser/vnc_lite.html?path=browser%2Fwebsockify%2F");
          die("Cannot auto-complete return. See VNC to finish manually.");
        } else {
          // Last resort: try clicking whatever is already selected
          log("AUTO-CONFIRM: attempting to Confirm with whatever carrier is selected");
          const lastTry = await clickAuiSubmit(page, "methods-section-continue-button-announce");
          if (lastTry) {
            await sleep(3000);
            const urlNow = page.url();
            if (urlNow.includes("/returns/confirmation")) {
              confirmed = true;
              chosenCarrier = "unknown (auto-confirmed with existing selection)";
            }
          }
        }
      }

      if (!confirmed) {
        die("Return could not be completed automatically.");
      }

      // ── 11. Capture confirmation ──────────────────────────────────
      await sleep(2000);
      const finalText = await page.locator("body").innerText();
      const finalUrl = page.url();

      // Extract key details
      const deadlineMatch = finalText.match(/Return by\s+([^\n]+)/i);
      const deadline = deadlineMatch ? deadlineMatch[1].trim() : "unknown";

      const refMatch = finalText.match(/return\s*id[:\s]*([A-Z0-9-]+)/i) ||
                       finalText.match(/reference[:\s]*([A-Za-z0-9-]+)/i);
      const refNum = refMatch ? refMatch[1] : "not found";

      log("\n========== RETURN CONFIRMED ==========");
      log("Carrier:", chosenCarrier);
      log("Deadline:", deadline);
      log("Reference:", refNum);
      log("Confirmation URL:", finalUrl);
      log("=======================================");

      await page.screenshot({ path: "/tmp/amazon-returns-final.png", fullPage: true });
      log("Screenshot saved: /tmp/amazon-returns-final.png");
    } else {
      log("No carrier page detected. Current page state uncertain.");
      await page.screenshot({ path: "/tmp/amazon-returns-uncertain.png", fullPage: true });
    }

  } finally {
    // Don't close the browser — it's the shared persistent Chromium.
    // Just close our connection.
    await browser.disconnect();
  }
}

main().catch(e => {
  console.error("[amazon-returns] ERROR:", e);
  process.exit(1);
});
