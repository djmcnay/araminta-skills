#!/usr/bin/env node
/**
 * Beanz Checkout CLI — full flow up to payment (stage 3)
 * Usage: node beanz-basket-cli.js <product-slug-or-url> [options]
 *
 * Options:
 *   --checkout            Continue through checkout to payment page (stage 3)
 *   --subscription        Order as subscription instead of one-time
 *   --grind <name>        Grind preference: "Whole bean" or "Ground" (default: "Whole bean")
 *   --size <grams>        Bag size: "250" or "1000" (default: "1000")
 *   --bags <n>            Number of bags (default: 1, max 5)
 *   --freq <weeks>        Subscription frequency: 1,2,4,6,8 (default: 2)
 *   --second <product>    Add a 2nd different coffee to basket (rarely the same)
 *   --show                Ensure page is visible on VNC (bringToFront)
 *   --dry-run             Navigate and configure but do NOT click Subscribe/Add
 */

const { chromium } = require("playwright");

// ─── Config ──────────────────────────────────────────────────────────
const BEANZ_BASE = "https://www.beanz.com/en-gb";
const CDP_URL = process.env.BEANZ_CDP_URL || "http://localhost:9222";
const TIMEOUT_MS = 30_000;

// Algolia credentials from env vars (see SKILL.md for discovery instructions)
const ALGOLIA_APP_ID = process.env.BEANZ_ALGOLIA_APP_ID || "";
const ALGOLIA_API_KEY = process.env.BEANZ_ALGOLIA_API_KEY || "";
const ALGOLIA_INDEX = process.env.BEANZ_ALGOLIA_INDEX || "Beanz_UK";
const ALGOLIA_URL = `https://${ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/${ALGOLIA_INDEX}/query`;

function log(...args) { console.log("[beanz-basket]", ...args); }
function die(msg) { console.error("[beanz-basket] FATAL:", msg); process.exit(1); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/**
 * Parse CLI args
 */
function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    product: args[0] || null,
    checkout: false,
    subscription: false,
    grind: "Whole bean",
    sizeG: "1000",
    bags: 1,
    freq: 2,
    second: null,
    show: false,
    dryRun: false,
  };
  for (let i = 1; i < args.length; i++) {
    const a = args[i];
    if (a === "--checkout") parsed.checkout = true;
    else if (a === "--subscription") parsed.subscription = true;
    else if (a === "--grind") parsed.grind = args[++i] || "Whole bean";
    else if (a === "--size") parsed.sizeG = args[++i] || "1000";
    else if (a === "--bags") parsed.bags = parseInt(args[++i] || "1", 10);
    else if (a === "--freq") parsed.freq = parseInt(args[++i] || "2", 10);
    else if (a === "--second") parsed.second = args[++i] || null;
    else if (a === "--show") parsed.show = true;
    else if (a === "--dry-run") parsed.dryRun = true;
  }
  return parsed;
}

/**
 * Build product URL from user input.
 */
async function resolveProductUrl(browser, raw) {
  if (!raw) die("No product specified.");
  if (raw.startsWith("http")) return raw;
  if (raw.includes("/") && raw.endsWith(".html")) {
    const path = raw.startsWith("/") ? raw : `/${raw}`;
    if (path.includes("/coffee/")) return `${BEANZ_BASE}${path}`;
    return `${BEANZ_BASE}/coffee${path}`;
  }
  log("Searching for coffee:", raw);
  const ctx = browser.contexts()[0] || await browser.newContext();
  const page = await ctx.newPage();
  try {
    const res = await page.evaluate(async (q) => {
      const resp = await fetch(
        ALGOLIA_URL,
        {
          method: "POST",
          headers: {
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query: q, hitsPerPage: 5 }),
        }
      );
      return resp.json();
    }, raw);
    const hits = res.hits || [];
    if (hits.length === 0) die(`No coffee found matching "${raw}"`);
    const match = hits[0];
    const url = match.PDP_URL || match.url;
    if (!url) die("Search result has no product URL");
    log("Resolved to:", url);
    return url.startsWith("http") ? url : `https://www.beanz.com${url}`;
  } finally {
    await page.close().catch(() => {});
  }
}

/**
 * Select option by exact button text (first <p> child or innerText prefix).
 */
async function selectOptionByText(page, desiredText) {
  const buttons = await page.locator('button.option').all();
  for (const btn of buttons) {
    const firstP = await btn.locator('p').first().innerText().catch(() => "");
    const txt = firstP || (await btn.innerText().catch(() => ""));
    if (txt.trim().toLowerCase() === desiredText.toLowerCase()) {
      const cls = await btn.getAttribute("class");
      if (cls && cls.includes("option--active")) {
        log("Already selected:", desiredText);
        return true;
      }
      await btn.click();
      await sleep(800);
      log("Selected:", desiredText);
      return true;
    }
  }
  log("Could NOT find button with text:", desiredText);
  return false;
}

/**
 * Click option by partial visible text.
 */
async function clickOption(page, labelSubstring) {
  const buttons = await page.locator('button.option').all();
  for (const btn of buttons) {
    const txt = await btn.innerText().catch(() => "");
    if (txt.toLowerCase().includes(labelSubstring.toLowerCase())) {
      const cls = await btn.getAttribute("class");
      if (cls && cls.includes("option--active")) {
        log("Already selected:", labelSubstring);
        return true;
      }
      await btn.click();
      await sleep(800);
      log("Selected:", labelSubstring);
      return true;
    }
  }
  return false;
}

/**
 * Configure product options on PDP.
 */
async function configureProduct(page, opts) {
  // Purchase type
  if (opts.subscription) {
    await clickOption(page, "Subscription");
  } else {
    await clickOption(page, "One-Time Purchase");
  }

  // Grind
  const grindTarget = opts.grind === "Whole bean" ? "Whole bean" : "Ground";
  const grindOk = await selectOptionByText(page, grindTarget);
  if (!grindOk) log("WARNING: could not select grind:", grindTarget);

  // Size
  const sizeMap = { "200": "200 gr", "250": "250 gr", "1000": "1 kg" };
  const sizeLabel = sizeMap[opts.sizeG] || `${opts.sizeG} gr`;
  const sizeOk = await selectOptionByText(page, sizeLabel);
  if (!sizeOk) log("WARNING: could not select size:", sizeLabel);

  // Bags
  if (opts.bags > 1) {
    const bagLabel = opts.bags === 1 ? "1 bag" : `${opts.bags} bags`;
    const bagOk = await selectOptionByText(page, bagLabel);
    if (!bagOk) log("WARNING: could not select bag count:", bagLabel);
  }

  // Frequency (subscription only)
  if (opts.subscription) {
    const freqLabelMap = { 1: "1 week", 2: "2 weeks", 4: "4 weeks", 6: "6 weeks", 8: "8 weeks" };
    const freqLabel = freqLabelMap[opts.freq] || `${opts.freq} weeks`;
    const freqOk = await selectOptionByText(page, freqLabel);
    if (!freqOk) log("WARNING: could not select frequency:", freqLabel);
  }
}

/**
 * Add configured product to cart.
 */
async function addToCart(page, opts) {
  const ctaBtn = page.locator(".add-to-cart-btn").first();
  const ctaVisible = await ctaBtn.isVisible().catch(() => false);
  if (!ctaVisible) die("Add to cart button not visible.");

  const ctaText = await ctaBtn.innerText().catch(() => "Unknown");
  log("Clicking CTA:", ctaText.trim());
  await ctaBtn.click();
  await sleep(3000);

  // Navigate to cart page to verify
  const CART_URL = "https://www.beanz.com/transaction/en-gb/cart";
  await page.goto(CART_URL, { waitUntil: "domcontentloaded" });
  // Wait for cart items to appear (Remove button is reliable indicator)
  try {
    await page.waitForSelector('button:has-text("Remove")', { timeout: 5000 });
    log("Item confirmed in cart (Remove button visible)");
    return { added: true, ctaText: ctaText.trim(), url: page.url() };
  } catch {
    // No Remove button found — cart might be empty
    const currentUrl = page.url();
    if (/sign-in|login|auth/.test(currentUrl)) {
      return { added: false, reason: "pending-auth", url: currentUrl };
    }
    // One more check: does page show an empty cart message?
    const bodyText = await page.evaluate(() => document.body?.innerText || "");
    if (/your cart is empty/i.test(bodyText)) {
      return { added: false, reason: "cart-empty-verified", url: currentUrl };
    }
    return { added: false, reason: "no-remove-btn", url: currentUrl };
  }
}

/**
 * Parse cart page for summary.
 */
async function readCartSummary(page) {
  const body = await page.evaluate(() => document.body.innerText);
  const lines = body.split("\n").map(l => l.trim()).filter(Boolean);

  const hasDiscount = body.includes("% off coffee discount") || body.includes("% OFF");
  const hasStandardDelivery = body.includes("Standard Delivery") || body.includes("Free");
  const isDeliveryFree = body.includes("Free") && body.includes("Delivery");

  // Extract order total
  const totalMatch = body.match(/Order Total[\s:£]*([\d.,]+)/i);
  const orderTotal = totalMatch ? totalMatch[1] : null;

  // Extract discount amount
  const discountMatch = body.match(/Discount[\s:£-]*([\d.,]+)/i);
  const discountAmount = discountMatch ? discountMatch[1] : null;

  return { hasDiscount, hasStandardDelivery, isDeliveryFree, orderTotal, discountAmount, body: body.substring(0, 500) };
}

/**
 * Continue to checkout and verify stages.
 */
async function proceedToCheckout(page) {
  const continueBtn = await page.locator("button:has-text('Continue to Checkout')").first();
  if (!await continueBtn.isVisible().catch(() => false)) {
    return { reached: false, reason: "checkout-button-not-found" };
  }
  await continueBtn.click();
  await sleep(4000);

  // Verify we're on checkout page
  const url = page.url();
  if (!url.includes("/checkout")) {
    return { reached: false, reason: "not-on-checkout", url };
  }

  const body = await page.evaluate(() => document.body.innerText);

  // Verify shipping method
  const hasStandardDelivery = body.includes("Standard Delivery");

  // Verify stage 3 — Payment section
  const hasPayment = body.includes("Payment") || body.includes("Payment Method") || body.includes("Credit/Debit Card");
  const hasBuyNow = body.includes("Buy now");

  // Order summary on checkout
  const hasDiscount = body.includes("% off coffee discount") || body.includes("% OFF");
  const totalMatch = body.match(/Order Total[\s:£]*([\d.,]+)/i);
  const orderTotal = totalMatch ? totalMatch[1] : null;

  return {
    reached: true,
    url,
    stage3: hasPayment && hasBuyNow,
    deliveryOk: hasStandardDelivery,
    discountOk: hasDiscount,
    orderTotal,
    body: body.substring(0, 600),
  };
}

// ─── Main ────────────────────────────────────────────────────────────
async function main() {
  const opts = parseArgs();
  if (!opts.product) {
    die("Usage: node beanz-basket-cli.js <product-url-or-name> [--checkout] [--subscription] [--grind 'Whole bean'] [--size 1000] [--bags 1] [--freq 2] [--second <product>] [--show] [--dry-run]");
  }

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

  if (opts.show) {
    await page.bringToFront();
    log("Page brought to front (should be visible on VNC)");
  }

  const report = {
    product1: null,
    product2: null,
    cart: null,
    checkout: null,
  };

  try {
    // ── Product 1 ────────────────────────────────────────────────
    const url1 = await resolveProductUrl(browser, opts.product);
    log("Navigating to product 1:", url1);
    await page.goto(url1, { waitUntil: "domcontentloaded" });
    await sleep(3000);

    const title1 = await page.locator("h1").first().innerText().catch(() => "Unknown");
    const roaster1 = await page.locator("h1").first().evaluate((el) => {
      const prevLink = el.previousElementSibling;
      return prevLink?.tagName === "A" ? prevLink.innerText.trim() : "";
    }).catch(() => "");
    log("Product 1:", title1.trim(), roaster1 ? `(${roaster1.trim()})` : "");
    report.product1 = { title: title1.trim(), roaster: roaster1.trim(), url: page.url() };

    await configureProduct(page, opts);

    // Price read
    const priceText = await page.locator("h1 + p, h1 ~ p, [data-testid*='price']").first().innerText().catch(() => "");
    log("Page price:", priceText.trim());

    if (opts.dryRun) {
      log("DRY RUN — stopping before add-to-cart");
      console.log(JSON.stringify({ success: "dry-run", report }, null, 2));
      process.exit(0);
    }

    const addResult1 = await addToCart(page, opts);
    if (!addResult1.added) {
      die(`Add to cart failed: ${addResult1.reason} at ${addResult1.url}`);
    }
    log("Product 1 added to cart:", addResult1.ctaText);

    // ── Product 2 (2nd bag, different coffee) ────────────────────
    if (opts.second) {
      const url2 = await resolveProductUrl(browser, opts.second);
      log("Navigating to product 2:", url2);
      await page.goto(url2, { waitUntil: "domcontentloaded" });
      await sleep(3000);

      const title2 = await page.locator("h1").first().innerText().catch(() => "Unknown");
      const roaster2 = await page.locator("h1").first().evaluate((el) => {
        const prevLink = el.previousElementSibling;
        return prevLink?.tagName === "A" ? prevLink.innerText.trim() : "";
      }).catch(() => "");
      log("Product 2:", title2.trim(), roaster2 ? `(${roaster2.trim()})` : "");
      report.product2 = { title: title2.trim(), roaster: roaster2.trim(), url: page.url() };

      // Configure product 2 with same options
      await configureProduct(page, opts);

      const addResult2 = await addToCart(page, opts);
      if (!addResult2.added) {
        die(`Product 2 add-to-cart failed: ${addResult2.reason}`);
      }
      log("Product 2 added to cart:", addResult2.ctaText);
    }

    // ── Cart Summary ────────────────────────────────────────────
    log("Reading cart summary...");
    await page.goto(`${BEANZ_BASE}/transaction/en-gb/cart`, { waitUntil: "domcontentloaded" });
    await sleep(2000);
    const cartSummary = await readCartSummary(page);
    report.cart = cartSummary;
    log("Discount applied:", cartSummary.hasDiscount);
    log("Standard Delivery:", cartSummary.hasStandardDelivery);
    log("Delivery Free:", cartSummary.isDeliveryFree);
    log("Order Total:", cartSummary.orderTotal ? `£${cartSummary.orderTotal}` : "unknown");

    if (!cartSummary.hasDiscount) {
      log("NOTE: No loyalty discount detected in cart.");
    }
    if (!cartSummary.isDeliveryFree) {
      log("NOTE: Delivery is NOT free. Consider adding a 2nd bag via --second.");
    }

    // ── Checkout ───────────────────────────────────────────────
    if (opts.checkout) {
      log("Proceeding to checkout...");
      const checkoutResult = await proceedToCheckout(page);
      report.checkout = checkoutResult;

      if (checkoutResult.reached) {
        log("=== CHECKOUT VERIFICATION ===");
        log("Stage 3 (Payment):", checkoutResult.stage3 ? "YES" : "NO");
        log("Standard Delivery:", checkoutResult.deliveryOk ? "YES" : "NO");
        log("Discount on checkout:", checkoutResult.discountOk ? "YES" : "NO");
        log("Order Total:", checkoutResult.orderTotal ? `£${checkoutResult.orderTotal}` : "unknown");
      } else {
        log("ERROR: Could not reach checkout:", checkoutResult.reason);
      }
    }

    console.log(JSON.stringify({ success: true, report }, null, 2));
  } catch (err) {
    log("ERROR:", err.message);
    await page.screenshot({ path: "/tmp/beanz-basket-error.png", fullPage: true }).catch(() => {});
    die(err.message);
  } finally {
    // Keep page open for VNC viewing; don't close browser
    log("Done. Browser kept open for VNC viewing.");
  }
}

main().catch((err) => {
  console.error("[beanz-basket] UNCAUGHT:", err);
  process.exit(1);
});