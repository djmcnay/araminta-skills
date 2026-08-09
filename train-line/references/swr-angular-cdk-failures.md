# SWR Delay Repay — Angular Material/CDK Automation Pitfalls (Pi 5)

Session: 2026-05-21. Context: Araminta tried to file a claim for the user on the SWR Delay Repay portal from the Pi 5 (8GB, headless Chromium).

## Executive Summary

The SWR make-claim page is built with Angular Material (mat-stepper, mat-autocomplete, mat-datepicker, mat-radio-button) and CDK overlays (cdk-overlay-backdrop, cdk-option). From the Pi, the Hermes browser tool (Camoufox/Chromium CDP) could **log in and navigate** but could **not click through the form** because Angular overlays intercept pointer events at every step. The correct tool is **Playwright local Chromium** (`python3 -m playwright`, NOT Hermes browser_click/CDP).

---

## 1. Environment Discovery

- **Playwright** is NOT installed by default on the Pi Python system. Install: `pip3 install playwright --break-system-packages && playwright install chromium`
- **Playwright location**: installs under `~/.local/lib/python3.11/site-packages/playwright/` and `~/.cache/ms-playwright/chromium_headless_shell-*/`
- **Do NOT use Camoufox** for SWR claims — Camoufox's accessibility tree re-orders elements and hides Angular overlays, making it impossible to interact with autocomplete dropdowns.
- **Do NOT use Hermes browser_click/CDP** for Angular Material forms — the overlay intercepts every click.

---

## 2. Pitfall: Playwright `.nth()` Index Drift

On the make-claim page, `#mat-input-1` is From, `#mat-input-2` is To, `#mat-input-3` is Time. But the accessibility tree reports them as combobox `@e30`, `@e31`, `@e32` with values that can swap. **Always use stable `id=` selectors, never `.nth()` on autocomplete inputs.**

```python
# WRONG (position depends on hidden tab panels)
from_input = page.locator('input.mat-autocomplete-trigger').nth(1)

# RIGHT (stable across tab switches)
from_input = page.locator('#mat-input-1')
```

---

## 3. Pitfall: Date Picker is READONLY

The date field (`#mat-input-0`) is a `mat-datepicker-input` with `readonly="true"`. Playwright `.fill()` fails with "element is not editable". CDP `browser_type`/`browser_click` opens a calendar overlay that intercepts all subsequent clicks.

**Symptom:**
- `Locator.fill: Timeout 30000ms exceeded. element is not editable`
- Or: `Locator.click: cdk-overlay-backdrop intercepts pointer events`

**Fix — Pre-select date from account summary:**
```python
await page.goto("https://delayrepay.southwesternrailway.com/en/account")
await page.locator('button:has-text("21 May 2026")').click()
await page.wait_for_url("**/make-claim**", timeout=15000)
```

**Alternative — Force value via JS (after dismissing overlays):**
```python
await page.evaluate("""
    () => {
        const d = document.querySelector('#mat-input-0');
        d.value = '21/05/2026';
        d.dispatchEvent(new Event('input', {bubbles: true}));
    }
""")
```

---

## 4. Pitfall: Angular Autocomplete Requires Keyboard Events, Not Fill

`page.fill()` sets the value but does not trigger Angular Material's `input` event chain. The dropdown (`mat-option`) never appears.

**Symptom:** No `mat-option` elements visible after `.fill()`.

**Fix:**
```python
await from_input.click()
await page.keyboard.type("Haslemere")  # NOT .fill()
await page.wait_for_timeout(2500)
```

---

## 5. Pitfall: CDP Target Attach Failures

Attempting to use `browser_cdp(method='Runtime.evaluate', target_id=...)` after page navigation fails with:
> `Target.attachToTarget failed: No target with given id found`

**Fix:** Let Hermes re-acquire targets. Or better: switch to Playwright entirely.

---

## 6. Fallback Decision Tree

If the automation script fails on the Pi:

1. **Retry once** on the Mac via Tailscale (better browser rendering, different Playwright engine)
2. **If still failing after 3 retries** — switch to **manual filing** and give the user the claim summary
3. **Never spend >5 minutes debugging Angular overlay issues from the Pi** — it's not a headless-friendly SPA

---

## 7. Correct Claim Summary for Manual Filing

When automation aborts, produce this exact format:

| Field | Value |
|-------|-------|
| Date | 21 May 2026 |
| From | Haslemere |
| To | London Waterloo |
| Leaving at | 0931 |
| Delay | 120+ minutes |
| Ticket type | Return (Off-Peak) |
| Ticket ref | TTBQ7D9FEQF |
| Compensation | BACS, sort code [sort-code] |

Store claim evidence with `delay_repay.py store` before attempting automation.
