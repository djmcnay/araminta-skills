#!/usr/bin/env node
/**
 * Amazon Basket Add CLI with Variant Selection
 * Usage: node amazon-basket-cli.js <ASIN> [quantity] [--variant "label substring"]
 *
 * Connects to persistent Chromium via CDP (:9222). Supports:
 * 1. Direct child-ASIN: add immediately (parent passes child ASIN)
 * 2. Parent ASIN + --variant: load parent page, click matching variant, then add
 *
 * Variant matching is fuzzy on the visible twister button text (e.g.
 * "24 Count", "Raspberry", "Pack of 2"). The script extracts all
 * variant labels + prices and picks the closest match.
 */

const { chromium } = require("playwright");

// ─── Config ──────────────────────────────────────────────────────────
const AMAZON_DOMAIN = "https://www.amazon.co.uk";
const CDP_URL = process.env.AMAZON_CDP_URL || "http://localhost:9222";
const TIMEOUT_MS = 30_000;

function log(...args) { console.log("[amazon-basket]", ...args); }
function die(msg) { console.error("[amazon-basket] FATAL:", msg); process.exit(1); }

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/**
 * Parse CLI args: first positional = ASIN, second = quantity (optional),
 * --variant flag takes the next positional as the variant query.
 */
function parseArgs() {
  const args = process.argv.slice(2);
  let asin = null, quantity = 1, variantQuery = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--variant" || args[i] === "-v") {
      variantQuery = args[++i] || null;
    } else if (!asin) {
      asin = args[i];
    } else if (!isNaN(parseInt(args[i], 10))) {
      quantity = parseInt(args[i], 10);
    }
  }
  return { asin, quantity, variantQuery };
}

/**
 * Extract variant options from an Amazon product page.
 * Returns array of { id, label, price, unitPrice }.
 */
async function extractVariants(page) {
  return page.evaluate(() => {
    const results = [];
    const seen = new Set();

    // Helper: clean label text (first line only)
    function cleanLabel(text) {
      return text.split(/\n/)[0].trim();
    }

    // Helper: extract price from text block
    function extractPrice(text) {
      const m = text.match(/£([0-9,.]+)/);
      return m ? `£${m[1]}` : "";
    }

    // Helper: extract unit price
    function extractUnit(text) {
      const m = text.match(/(£[0-9,.]+\s*\/\s*[^)]+)/);
      return m ? m[1].trim() : "";
    }

    // Strategy 1: ID-based twister buttons (size_name_X, flavour_name_X, etc.)
    const twisterIds = ['size', 'colour', 'flavor', 'flavour', 'scent', 'pack', 'style', 'count'];
    const sel = twisterIds.map(p => `[id^="${p}_name_"]`).join(", ");
    document.querySelectorAll(sel).forEach(el => {
      // Skip announce spans
      if (el.id.endsWith("-announce")) return;
      const text = el.innerText?.trim() || "";
      const label = cleanLabel(text);
      if (seen.has(label)) return;
      seen.add(label);
      const price = extractPrice(text);
      const unitPrice = extractUnit(text);

      // Find ASIN: check data-asin on the element or a child/input
      let asin =
        el.getAttribute("data-asin") ||
        el.querySelector("[data-asin]")?.getAttribute("data-asin") ||
        el.closest("[data-asin]")?.getAttribute("data-asin") ||
        "";

      results.push({ id: el.id, label, price, unitPrice, asin, element: "twister" });
    });

    // Strategy 2: Generic .a-button-toggle class —
    // only if twister strategy above found nothing (avoid duplicates + noise)
    if (results.length === 0) {
      document.querySelectorAll('.a-button-toggle:not([id*="-announce"])').forEach(el => {
        const text = el.innerText?.trim() || "";
        const lines = text.split(/\n/).filter(l => l.trim());
        const label = lines[0] || "";
        if (seen.has(label) || label.length < 2) return;

        // Reject obvious UI noise
        const lowerLabel = label.toLowerCase();
        const noiseWords = [
          'load more','resume response','create a free account','try today',
          'sign in','learn more','see all','next page','previous page',
          'subscribe','buy now','add to list','see details'
        ];
        if (noiseWords.some(w => lowerLabel.includes(w))) return;

        // Reject pagination controls (single number like "4+" or "2")
        if (/^[0-9]+\+$/.test(label)) return;

        seen.add(label);
        const price = extractPrice(text);
        const unitPrice = extractUnit(text);

        let asin =
          el.getAttribute("data-asin") ||
          el.querySelector("[data-asin]")?.getAttribute("data-asin") ||
          el.closest("[data-asin]")?.getAttribute("data-asin") ||
          "";

        results.push({ id: el.id, label, price, unitPrice, asin, element: "toggle" });
      });
    }

    // Strategy 3: Select dropdowns
    document.querySelectorAll('select').forEach(s => {
      const name = (s.name || s.id || s.getAttribute("aria-label") || "").toLowerCase();
      if (/size|colour|color|flavour|flavor|scent|style|count|pack/i.test(name)) {
        for (const opt of s.options) {
          const label = opt.text.trim();
          if (seen.has(label)) continue;
          seen.add(label);
          const price = extractPrice(label);
          results.push({ id: null, selectId: s.name || s.id, label, price, unitPrice: "", asin: opt.value || "", element: "select" });
        }
      }
    });

    return results;
  });
}

/**
 * Fuzzy match variant query against available options.
 * Returns the best-matching variant object or null.
 */
function matchVariant(variants, query) {
  const q = query.toLowerCase();
  let best = null, bestScore = 0;

  for (const v of variants) {
    const label = v.label.toLowerCase();
    let score = 0;

    // Exact match (after normalising spaces)
    if (label === q) score = 1000;
    // Starts with query
    else if (label.startsWith(q)) score = 500;
    // Contains all words (in any order)
    else {
      const qWords = q.split(/\s+/).filter(w => w.length >= 2);
      const labelWords = label.split(/\s+/);
      const matches = qWords.filter(w => labelWords.some(lw => lw.includes(w) || w.includes(lw))).length;
      score = matches * 100;
      // Bonus for exact word match
      if (labelWords.includes(q)) score += 50;
    }

    if (score > bestScore) {
      bestScore = score;
      best = v;
    }
  }
  return bestScore >= 100 ? best : null;
}

async function clickVariant(page, variant) {
  if (variant.element === "twister" || variant.element === "toggle") {
    const btn = page.locator(`#${variant.id}`);
    const visible = await btn.isVisible().catch(() => false);
    if (!visible) return false;
    await btn.click();
    await sleep(2000);
    return true;
  }

  if (variant.element === "select") {
    const sel = page.locator(`select[name="${variant.selectId}"], select#${variant.selectId}`);
    const visible = await sel.isVisible().catch(() => false);
    if (!visible) return false;
    await sel.selectOption(variant.asin || variant.label);
    await sel.evaluate((el) => {
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await sleep(2000);
    return true;
  }

  return false;
}

// ─── Main ────────────────────────────────────────────────────────────
async function main() {
  const { asin, quantity, variantQuery } = parseArgs();
  if (!asin) die(
    "Usage: node amazon-basket-cli.js <ASIN> [quantity] [--variant \"label substring\"]"
  );

  log("Connecting to persistent Chromium at", CDP_URL);
  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
  } catch (err) {
    die(`Cannot connect to CDP at ${CDP_URL}: ${err.message}`);
  }

  const context = browser.contexts()[0] || await browser.newContext();
  const existingPages = context.pages();
  const page = existingPages[existingPages.length - 1] || await context.newPage();
  page.setDefaultTimeout(TIMEOUT_MS);

  try {
    // ── 1. Navigate ──────────────────────────────────────────────
    const productUrl = `${AMAZON_DOMAIN}/dp/${asin}`;
    log("Navigating to", productUrl);
    await page.goto(productUrl, { waitUntil: "domcontentloaded" });
    await sleep(2000);  // Give Amazon JS a moment to hydrate

    // ── 2. Verify logged in ─────────────────────────────────────
    const loggedInCheck = await page
      .evaluate(() => /hello,\s*david/i.test(document.body.innerText))
      .catch(() => false);
    if (!loggedInCheck)
      die("Not logged in as David. Session may have expired.");
    log("Logged in as David");

    // ── 3. Extract title + price ─────────────────────────────────
    // Amazon's h1 includes accessibility shortcut text — filter to h1#title
    const title = await page
      .locator("#productTitle, #title")
      .first()
      .innerText()
      .catch(() => "Unknown product");
    const priceOffscreen = await page
      .locator(
        "#corePrice_feature_div .a-price .a-offscreen, " +
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen, " +
        "#apex_desktop .a-price .a-offscreen, " +
        ".a-price .a-offscreen"
      )
      .first()
      .innerText()
      .catch(() => "");
    log("Product:", title.trim().substring(0, 80));
    log("Price:", priceOffscreen.trim() || "price unknown");

    // ── 4. Variant selection (if requested) ─────────────────────
    let selectedVariant = null;
    let variantPrice = null;
    if (variantQuery) {
      log("Looking for variant matching:", variantQuery);
      const variants = await extractVariants(page);
      log(`Found ${variants.length} variant(s)`);

      for (const v of variants) {
        log(`  → ${v.label} @ ${v.price || "no price"}  (id=${v.id})`);
      }

      selectedVariant = matchVariant(variants, variantQuery);
      if (!selectedVariant) {
        die(`No variant matched "${variantQuery}". See list above.`);
      }
      log("Matched variant:", selectedVariant.label, "@", selectedVariant.price);

      const clicked = await clickVariant(page, selectedVariant);
      if (!clicked) die(`Failed to click variant ${selectedVariant.id}`);

      // Verify page updated
      await sleep(1500);
      variantPrice = await page
        .locator(
          "#corePrice_feature_div .a-price .a-offscreen, " +
          "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen"
        )
        .first()
        .innerText()
        .catch(() => "");
      if (variantPrice) log("New price after variant selection:", variantPrice.trim());
    }

    // ── 5. Basket count before ──────────────────────────────────
    const basketBefore = await page
      .locator("#nav-cart-count")
      .innerText()
      .catch(() => "0");
    const beforeCount = parseInt(basketBefore.trim(), 10) || 0;
    log("Basket count before:", beforeCount);

    // Use variant price for reporting if we selected one
    const finalPrice = selectedVariant && variantPrice
      ? variantPrice.trim()
      : priceOffscreen.trim() || "price unknown";

    // ── 6. Click Add to Basket ──────────────────────────────────
    // After variant click, the buy box may re-render. Wait for the
    // real Add to Basket button to become visible.
    const addBtnSelectors = [
      '#add-to-cart-button',
      'input[name="submit.add-to-cart"]',
      '[name="submit.add-to-cart"]',
      'input#add-to-cart-button',
      '#desktop_qualifiedBuyBox #add-to-cart-button',
    ];

    let addBtn = null;
    let btnVisible = false;

    for (let attempt = 0; attempt < 5; attempt++) {
      for (const sel of addBtnSelectors) {
        const el = page.locator(sel).first();
        btnVisible = await el.isVisible().catch(() => false);
        if (btnVisible) {
          addBtn = el;
          log("Found add button via:", sel);
          break;
        }
      }
      if (btnVisible) break;
      log("Waiting for buy box to render (attempt", attempt + 1, "/5)...");
      await sleep(1000);
    }

    if (!addBtn || !btnVisible) {
      die("Add to Basket button not found on page after waiting.");
    }

    log("Clicking Add to Basket...");
    await addBtn.click();

    await sleep(2000);

    // ── 7. Verify basket incremented ─────────────────────────────
    const basketAfter = await page
      .locator("#nav-cart-count")
      .innerText()
      .catch(() => basketBefore);
    const afterCount = parseInt(basketAfter.trim(), 10) || beforeCount;
    log("Basket count after:", afterCount);

    if (afterCount > beforeCount) {
      log("SUCCESS — added to basket");
      console.log(
        JSON.stringify({
          success: true,
          asin,
          title: title.trim(),
          price: finalPrice,
          variant: selectedVariant
            ? { label: selectedVariant.label, price: selectedVariant.price }
            : null,
          quantity,
          basketBefore: beforeCount,
          basketAfter: afterCount,
        })
      );
    } else {
      // Check if Amazon redirected to confirmation page
      const currentUrl = page.url();
      const pageTitle = await page.title();
      if (/confirm your action/i.test(pageTitle) || /cart\/add/i.test(currentUrl)) {
        log("INFO — confirmation page shown");
        console.log(
          JSON.stringify({
            success: "pending",
            asin,
            title: title.trim(),
            price: finalPrice,
            variant: selectedVariant
              ? { label: selectedVariant.label, price: selectedVariant.price }
              : null,
            quantity,
            basketBefore: beforeCount,
            basketAfter: afterCount,
            note: "Amazon requires confirmation. Check basket manually.",
            url: currentUrl,
          })
        );
      } else {
        log("WARNING — basket count did not change");
        console.log(
          JSON.stringify({
            success: false,
            asin,
            title: title.trim(),
            price: finalPrice,
            quantity,
            basketBefore: beforeCount,
            basketAfter: afterCount,
            note: "Basket count unchanged.",
          })
        );
        process.exit(1);
      }
    }
  } catch (err) {
    log("ERROR:", err.message);
    await page
      .screenshot({ path: "/tmp/amazon-basket-error.png", fullPage: true })
      .catch(() => {});
    die(err.message);
  } finally {
    if (existingPages.length === 0) await page.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((err) => {
  console.error("[amazon-basket] UNCAUGHT:", err);
  process.exit(1);
});
