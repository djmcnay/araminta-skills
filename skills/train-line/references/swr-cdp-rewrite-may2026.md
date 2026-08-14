# SWR Delay Repay — CDP Rewrite Notes (May 2026)

Session: 23 May 2026. the user walked through the form step-by-step on VNC while I demonstrated each failure.

## What Changed in This Session

### 1. The script MUST connect to CDP, not launch its own browser

The old `swr_claim_complete.py` launched a fresh headless Chromium:
```python
browser = await p.chromium.launch(headless=True, args=["--no-sandbox", ...])
```

This is wrong because:
- It ignores the already-logged-in persistent browser on port 9222
- It requires HERMES_PASSWORD env var (redundant when logged in)
- `--no-sandbox` is a bot tell
- It wastes time on login when the user is already authenticated

The correct approach:
```python
browser = await p.chromium.connect_over_cdp("http://localhost:9222")
```

Then navigate to `/en/account` — the user is already logged in.

### 2. `.nth()` selector drift IS real

The playbook claims `.nth(1)` and `.nth(2)` are "the CURRENT reliable approach". They are not.

During the live walkthrough, hidden panel inputs (`mat-input-11`, `-12`, `-13`) exist at negative x coordinates. `.nth(1)` happens to point to `#mat-input-4` (visible From field) but this is fragile — it depends on Angular's tab panel rendering order.

**Stable IDs verified on the live form:**
- `#mat-input-0` = Travel date (readonly)
- `#mat-input-1` = From station
- `#mat-input-2` = To station  
- `#mat-input-3` = Time

These IDs are stable and should be used exclusively. The playbook and SKILL.md claiming `.nth()` is reliable are **wrong**.

### 3. `keyboard.type()` vs `.fill()` on Angular autocomplete

Demonstrated on screen: `.fill("Haslemere")` → no dropdown. `keyboard.type("Haslemere")` → dropdown appears. This is correct in the existing references.

### 4. `force=True` on `mat-radio-button` works

The "Multiple tickets?" Yes/No radios:
- Standard `.click()` → worked in this session (unexpected — may vary by Angular build)
- `force=True` → always works
- `page.evaluate("...querySelector('input').click()")` → no state change

The playbook is correct that `force=True` is the reliable method.

### 5. Ticket type cards are `cdk-option ticket-medium`, NOT `mat-radio-button`

The playbook says ticket types are "radio buttons" and suggests `mat-radio-button` selectors. This is wrong.

On the live form, ticket types are `div.cdk-option.ticket-medium` cards (not radio buttons). They render as a grid of 6 cards: Paper, SWR Touch Smartcard, E-ticket/M-ticket, Oyster, Contactless, Non-SWR smartcard.

**Correct click method:** coordinate-based click on the `cdk-option` element using its bounding rect:
```python
rect = await element.evaluate("el => el.getBoundingClientRect()")
await page.mouse.click(rect['x'] + rect['width']/2, rect['y'] + rect['height']/2)
```

Fallback: `force=True` on `mat-card` filter.

### 6. Duration cards are `sr-ticket-duration` custom elements

After selecting E-ticket, duration options appear as custom `<sr-ticket-duration>` elements (not `mat-card` or `mat-radio-button`). They are at various y-positions: Single (~y=76), Return (~y=76), Rover (~y=76), etc.

**Correct click method:** iterate `sr-ticket-duration` elements, match text, click by coordinates.

### 7. Stepper navigation via `button[matsteppernext]`

The playbook correctly documents that these buttons render outside viewport. The reliable approach is:
```python
await page.evaluate("""
    ({txt}) => {
        for (const b of document.querySelectorAll('button[matsteppernext]')) {
            if (b.textContent.toLowerCase().includes(txt) && b.offsetHeight > 0) {
                b.click(); return true;
            }
        }
        return false;
    }
""")
```

### 8. `--submit` flag needed

the user explicitly wants the script to be able to submit without asking. The old script hard-halted at Review with:
```python
log("=== HALT ===")
log("Review page reached. DO NOT click Submit in automated mode.")
```

This is wrong per the user's instruction. Add `--submit` flag.

### 9. VNC is the fallback, not the primary

the user's phrase "halt with the pissing angular" is a **hard instruction after ~15 failed attempts**, not a suggestion to start with VNC. The primary strategy is programmatic automation. The fallback is manual/VNC.

## Skill Updates Required

1. **SKILL.md Part 3D** — fix contradictory selector advice (`.nth()` vs `#mat-input-*`)
2. **SKILL.md** — add CDP connection as primary method, remove standalone launch
3. **SKILL.md** — remove HERMES_PASSWORD from script header
4. **SKILL.md** — document `cdk-option ticket-medium` for ticket types
5. **SKILL.md** — document `sr-ticket-duration` for Single/Return
6. **SKILL.md** — add `--submit` flag documentation
7. **Playbook** — fix `.nth()` claims, add CDP section, add correct ticket type selectors
8. **Script** — replace `swr_claim_complete.py` with v2 template

## Files

- Template: `templates/swr-claim-complete-v2.py` — corrected full script
- This reference: `references/swr-cdp-rewrite-may2026.md`
