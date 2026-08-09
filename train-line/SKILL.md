---
name: train-line
description: UK train live departures, journey planning, and delay repay evidence management. Triggered by station names, journey planning, train times, delay repay mentions.
ownership: collab
tags: [uk-train, commute, travel, pricing]
---

# Train Line — UK Rail Skill

Three capabilities: **live departures**, **journey planning with pricing**, and **delay repay**.

## Quick Reference

All scripts live in `scripts/`. Run from skill directory or use absolute paths.

```bash
SKILL_DIR=<path-to-skill>
PYTHON=<path-to-python>
```

---

## Part 1: Live Departures

**Script:** `scripts/departures.py`

Uses the National Rail OpenLDBWS (Darwin) SOAP API. Token is embedded in the script.

### Station Aliases

Configured in `config/stations.json`. Add your own stations (home, work, etc.) with their CRS codes.

Any CRS code also works directly (e.g. `LIP`, `WAT`, `EUS`, `PAD`).

Example aliases (customise in stations.json):
- **home** → your nearest station
- **work / london** → London Waterloo (WAT)
- Any UK station by CRS code

### Commands

```bash
# Departures from a station (alias or CRS code)
$PYTHON $SKILL_DIR/scripts/departures.py home
$PYTHON $SKILL_DIR/scripts/departures.py WAT --rows 5

# Filter to specific destination (checks calling points, including intermediate stops)
$PYTHON $SKILL_DIR/scripts/departures.py home --to WAT

# Arrivals board
$PYTHON $SKILL_DIR/scripts/departures.py home --arrivals
```

### Parsing the output

The script outputs formatted text with:
- On time / N min late / N min early / Cancelled
- Delay reasons when available (e.g. "late running freight train")
- Platform info
- NRCC messages (engineering works, disruptions)

### When filtered departures return nothing

If `departures.py <station> --to <dest>` returns "No trains calling at X", this may be legitimate (late evening, no more services). But also:

1. Check the unfiltered board: `departures.py <station> --rows 10` — are there trains heading in the right direction?
2. Cross-check with MyTrainPal journey page: `mytrainpal.com/train-journey/{from}-to-{to}`
3. Generate journey planner links as a backup

### Handling future-date queries (e.g. "tomorrow's trains" or "next Thursday around 8am")

The Darwin SOAP API (departures.py) only returns **live** data for the current day. It cannot show schedules for future dates. To answer "what trains run tomorrow morning":

**Multi-source fallback chain:**

1. **Start with `journey.py --from <X> --to <Y> --date <DATE> --time <TIME> --validate`** — generates National Rail and MyTrainPal links for the specific date/time.

2. **If the National Rail link renders** (rare — it's a JS-heavy Next.js app): read the timetable from the extracted page content. In practice it usually doesn't render without a browser.

3. **Try MyTrainPal timetable page** via `web_extract`: `https://www.mytrainpal.com/train-journey/<from>-to-<to>`. This works for the generic route page showing pricing and a sample timetable, but often only shows evening/few trains, not the full daily schedule. Use as a **source for route patterns** (frequency, operator, journey time range).

4. **Web search for timetable patterns**: Search `"<from> to <to>" train timetable <year> weekday morning` or search known timetable sites (live-departures.info, operator JourneyCheck pattern). The key fact to discover is the **regular departure pattern** (e.g., hourly at xx:21 past the hour, direct, ~1h09m).

5. **Operator JourneyCheck** (e.g. `journeycheck.com/swr/search?from=<CRS>&to=<CRS>`): works via `web_extract` for current live data only. Cannot query future dates. Useful to confirm route calling points.

6. **As a last resort**: extract the timetable from Trainline's route page (`thetrainline.com/train-times/<from>-to-<to>`). This page is JS-heavy and won't render the timetable table without a browser, but the page metadata (first/last train, fastest journey, trains per day) can be extracted via `web_extract` and provides useful context.

**SWR Official Timetable PDFs (by route group):** These are the authoritative sources for each line. Download and extract text for the specific route:
- **PTT04** — Windsor, Staines and Feltham to London Waterloo
- **PTT06** — Guildford and Woking to London Waterloo
- **PTT10** — Basingstoke, Alton and Aldershot to London Waterloo
- **PTT16** — Weybridge via Staines to London Waterloo
- **PTT17** — Portsmouth and Haslemere to London Waterloo
- **PTT19** — Southampton and Winchester to London Waterloo
- **PTT20** — Exeter, Yeovil and Salisbury to London Waterloo
- **PTT28** — Weymouth and Bournemouth to London Waterloo
- **PTT02** — Reading and Ascot to London Waterloo

Base URL: `https://www.southwesternrailway.com/-/media/files/plan-my-journey/timetables/may-2026/pttXX-may-2026.pdf` (replace XX). Check SWR timetables page for current version and validity dates.

**Known failure modes:**
- National Rail journey planner is a Next.js app — `web_extract` returns only shell HTML/footers. Browser navigation times out consistently (CDP Page.enable timeout). Do not retry more than once.
- Omio (`omio.co.uk`) returns empty content from `web_extract` — do not use.
- Trainline's timetable table is JS-generated, not in static HTML.
- MyTrainPal only shows a few sample trains on the generic route page, not the full schedule.

### When the user says "going home", "going to work", etc.

1. Parse the alias from their message (using stations.json)
2. Run `departures.py <alias>`
3. Present the board concisely
4. If there's a significant delay, highlight it
5. If filtered results return nothing, fall back to checking unfiltered board + journey planner

---

## Part 2: Journey Planning and Pricing

**Script:** `scripts/journey.py`

Generates MyTrainPal journey page URLs for timetable and pricing. Can also scrape live prices via browser.

### Commands

```bash
# Basic journey with MyTrainPal link
$PYTHON $SKILL_DIR/scripts/journey.py --from lip --to wat

# With date/time and National Rail cross-validation
$PYTHON $SKILL_DIR/scripts/journey.py --from lip --to wat --date 2026-04-15 --time 09:00 --validate

# With price scraping (via anti-detection browser)
$PYTHON $SKILL_DIR/scripts/journey.py --from lip --to wat --price

# Return journey with custom return time
$PYTHON $SKILL_DIR/scripts/journey.py --from lip --to wat --return --return-time 20:00
```

### Output format

Returns MyTrainPal URLs formatted as bare URLs for cross-platform link compatibility.
The URLs use the pattern:
```
https://www.mytrainpal.com/train-journey/london-waterloo-to-isleworth
```

**Important:** MyTrainPal route URLs use **full station names** (e.g., `waterloo`, `islington`), NOT CRS codes (e.g., `wat`, `isl`). The `journey.py` script currently generates CRS-code URLs (e.g., `isleworth-to-wat`) which return 404. Working pattern: `isleworth-to-waterloo`, `liphook-to-london-waterloo`. When providing links manually, use the full-name format.

When `--price` is used, the script uses an anti-detection browser to scrape the actual single fare from MyTrainPal.

When `--validate` is used, also provides National Rail journey planner links for comparison.

### Pricing (default behaviour)

**The script defaults to providing MyTrainPal links.** These show timetables and prices natively on the page.

When the user explicitly asks for a price:
1. Send the MyTrainPal link immediately
2. Run with `--price` to scrape the actual fare
3. If scrape fails, the link already has the info they need

### Return journeys

The `--return` flag generates both outward and return links. Use `--return-time` to set the return departure (defaults to 18:00):
```bash
$PYTHON $SKILL_DIR/scripts/journey.py --from lip --to wat --return --return-time 20:00
```

### When the user says "I need to go from A to B"

1. Run `journey.py --from <A> --to <B> --validate`
2. Return the MyTrainPal link prominently
3. Mention National Rail link for cross-check
4. If they ask for prices, re-run with `--price`
5. **Never book tickets** — just provide links and prices

---

## Part 3: Delay Repay — Evidence Storage + Claim Filing

Two sub-capabilities: **storing evidence** (screenshots) and **filing claims** (browser automation).

### 3A: Evidence Storage

**Script:** `scripts/delay_repay.py`

Stores QR code screenshots from the user's phone for later claim filing.

```bash
# Store a screenshot
$PYTHON $SKILL_DIR/scripts/delay_repay.py store /path/to/screenshot.png --train-id "SWR 20:33 LIP→SOU" --notes "Rough running, 15 min late"

# List all stored evidence
$PYTHON $SKILL_DIR/scripts/delay_repay.py list

# Mark as filed
$PYTHON $SKILL_DIR/scripts/delay_repay.py mark-filed <id> --ref "DR-12345"
```

When the user sends a screenshot:
1. Save the image file to a temp location
2. Run `delay_repay.py store <path> --notes "<context>"`
3. Confirm storage with the entry ID
4. When the user wants to file, remind them which entries are pending

Images are stored in `data/delay_repay/` with unique IDs and a manifest (`index.json`).

---

### 3B: Filing a Delay Repay Claim (SWR Website Automation)

**Website:** https://www.southwesternrailway.com/contact-and-help/delay-repay
**Login:** User's email (stored securely in their harness config)
**Bank details:** User's sort code (default BACS compensation method)

#### Prerequisites
- Browser tool available (anti-detection browser or local Chromium)
- User provides: journey date, ticket image(s), whether single or return, whether 1 or 2 tickets
- User confirms same-day or provides specific date

#### Step-by-step Workflow

**For the current automation playbook (May 2026):** see `references/swr-claim-may-2026-playbook.md` — this has the working selectors, the calendar-click date pattern, and the unresolved ticket-type radio blocker with recommended mitigation.

**Template script:** `templates/swr-claim-preamble-up-to-add-ticket.py` — a working Playwright script that automates everything up to the "Add ticket" click, then pauses for manual ticket-type selection. Copy and modify per claim.

| Step | Action | Details |
|------|--------|---------|
| 1 | Navigate to SWR Delay Repay | `https://www.southwesternrailway.com/contact-and-help/delay-repay` |
| 2 | Click "Make a Claim" | Look for button/link on the page |
| 3 | Login | Email from user config, password from secure storage |
| 4 | Select journey date | User normally uses same day. Ask if unclear. |
| 5 | Fill journey details | Origin/destination stations |
| 6 | Fill approximate leaving time | User provides, or use planned departure from departures.py |
| 7 | Search for journey | Click search — results appear |
| 8 | Select the planned journey | **Always pick the fastest option** |
| 9 | Enter delay length | Calculate from actual vs planned. User usually knows. |
| 10 | Multiple tickets? | If user sends 1 ticket → single. If 2 → multiple. Default: ask. |
| 11 | Add first ticket | Click to add e-ticket image |
| 12 | Single or return? | User tells you, or check the ticket image for wording |
| 13 | Upload ticket image | Attach QR code / e-ticket image. System auto-fills ticket ref + price. Click Confirm. |
| 14 | Additional tickets? | If split-save or 2 tickets: click big **+** button, repeat steps 11–13 for second ticket |
| 15 | Confirm tickets → click "Compensation" | Proceed to compensation section |
| 16 | Compensation method | Pick **BACS** (default). Sort code from user config. Pre-filled if previously used. |
| 17 | Click "Review Claim" | Check all details |
| 18 | Click "Submit Claim" | Sends claim. Confirmation email goes to user's email. |

#### Important Notes
- **Ticket images:** The user sends e-ticket images. Use vision tool to read ticket type (single/return), reference, price, and route.
- **Split-save tickets:** Common — user may have 2 separate tickets for one journey. Check if they sent 2 images.
- **Delay calculation:** If the user says "15 minutes late", use that directly. Otherwise calculate from planned vs actual times.
- **Confirmation:** After submission, note the confirmation/reference number.
- **Mark as filed:** After successful submission, run `delay_repay.py mark-filed <id> --ref <reference>` for each ticket.

---

### 3C: Delay Repay Claim Links (Other TOCs)

If the claim is not with SWR:
- **Southern:** https://www.southernrailway.com/contact-and-help/delay-repay
- **Thameslink/Great Northern:** https://www.thameslinkrailway.com/contact-and-help/delay-repay
- **GWR:** https://www.gwr.com/help-and-support/refunds-and-compensation/delay-repay

Each TOC has its own form — process is similar but may differ in layout.

## Part 3D: SWR Claim Automation — Technical Implementation Notes

These notes capture the browser automation patterns discovered during live walkthrough sessions.

### Environment
- **Browser backend:** Persistent Chromium via CDP (`connect_over_cdp("http://localhost:9222")`). NOT a fresh launch. User is already logged in — no password needed.
- **Playwright:** Install per your environment. Import from your Python venv.
- **Viewport:** 1280x900 recommended

### CDP Connection (Primary)
```python
browser = await p.chromium.connect_over_cdp("http://localhost:9222")
ctx = browser.contexts()[0]
page = None
for pg in ctx.pages:
    if "delayrepay" in await pg.url() or "amazon" in await pg.url():
        page = pg
        break
if not page:
    page = await ctx.new_page()
```

Then navigate directly to `/en/account` — skips login entirely.

### Date Selection (Calendar Click — RELIABLE)

The date field (`#mat-input-0`) is `readonly`. JS injection triggers "Value entered is not valid". The ONLY reliable approach is opening the calendar and clicking the day.

```python
# Open calendar
toggle = page.locator('button.mat-datepicker-toggle-button, button[aria-label="Open calendar"]').first
if await toggle.is_visible(): await toggle.click()
await page.wait_for_timeout(1500)

# Click day number (text match e.g. "21")
for btn in await page.locator('button').all():
    if (await btn.inner_text()).strip() == "21":
        await btn.click(); break
await page.wait_for_timeout(1000)

# Verify: val = await page.locator('#mat-input-0').input_value() → '21/5/2026'
```

### Journey Tab — Filling From/To/Time (Angular Material Autocomplete)
The From/To comboboxes are Angular Material autocomplete triggers (`input.mat-autocomplete-trigger`). **Standard Playwright `fill()` does NOT trigger Angular form validation** — must use `keyboard.type()` character by character.

**Do NOT use `.nth()` on autocomplete inputs.** Hidden tab panels shift the index. Use stable IDs:
-   `#mat-input-0` = Travel date (READONLY — cannot `.fill()`, use calendar click)
-   `#mat-input-1` = From station
-   `#mat-input-2` = To station
-   `#mat-input-3` = Time

```python
from_input = page.locator('#mat-input-1')
await from_input.click()
await page.keyboard.type("Haslemere", delay=100)
await page.wait_for_timeout(2500)
await page.locator('mat-option').filter(has_text="HASLEMERE").first.click()

to_input = page.locator('#mat-input-2')
await to_input.click()
await page.keyboard.type("London Waterloo", delay=100)
await page.wait_for_timeout(2500)
await page.locator('mat-option').filter(has_text="LONDON WATERLOO [WAT]").first.click()

time_input = page.locator('#mat-input-3')
await time_input.click()
await time_input.keyboard.type("0931", delay=100)
```

**Dropdown options:** `mat-option` elements appear after typing. Text format: "STATION NAME [CRS]".

### Searching for Journeys
```python
await page.locator('#find-journey').click()  # Search button has id="find-journey"
await page.wait_for_timeout(8000)
```

**"A value is required" error:** Caused by Angular not registering `fill()` values. Use `keyboard.type()`.

### Selecting a Journey (cdk-listbox Options)
Results appear as `cdk-option` cards in a `cdk-listbox`. First result = fastest.

```python
await page.locator('div.cdk-option.selectable-journey-card').first.click()
```

### Delay Selection (cdk-listbox with mat-card options)
NOT radio buttons. These are `mat-card.cdk-option.delay-duration-card` elements.

```python
await page.locator('mat-card.cdk-option.delay-duration-card').filter(has_text="30 - 59").first.click()
```

Options: "Between 15-29 minutes", "Between 30-59 minutes", "Between 60-119 minutes", "120 minutes or more".

### Navigating Between Stepper Tabs
`button[matsteppernext]` buttons — there are 4. May render **outside viewport**. Use JS click:

```python
await page.evaluate("""
    () => {
        const btns = document.querySelectorAll('button[matsteppernext]');
        for (const b of btns) { if (b.textContent.includes('Ticket')) { b.click(); break; } }
    }
""")
```

### Ticket Tab — Multiple Tickets Radio
Standard `mat-radio-button` elements. Use JS to click:

```python
await page.evaluate("""
    () => {
        const r = [...document.querySelectorAll('mat-radio-button')]
            .find(x => x.querySelector('.mat-radio-label')?.textContent?.trim() === 'Yes');
        if(r) r.querySelector('label').click();
    }
""")
```

### Adding a Ticket (Add Ticket Card)
**It's a `mat-card`, not a `button`.** `<mat-card aria-label="Add ticket">` with `<mat-icon>add</mat-icon>`.

```python
add_card = page.locator('mat-card[aria-label="Add ticket"]')
await add_card.scroll_into_view_if_needed()
await add_card.click()
```

### Ticket Type Selection
After clicking "Add ticket", a "Ticket 1" section appears with clickable `mat-card` options:
Paper, SWR Touch Smartcard, **E-ticket/M-ticket**, Oyster, Contactless, Non-SWR smartcard

```python
await page.locator('mat-card').filter(has_text="E-ticket").first.click()
```

**If this fails after 3 attempts, try keyboard navigation:**
```python
await page.locator('mat-card').filter(has_text="E-ticket").first.focus()
await page.keyboard.press("Space")
```

**HARD HALT:** If neither programmatic approach works after a total of ~15 attempts on any Angular element, stop. Do not loop the same failures or exhaust the tool budget. Pivot to a headed browser and use the vision model. Manual intervention on the final step is acceptable.

### Common Pitfalls
1. **Never `fill()` on Angular autocomplete** — use `keyboard.type()` to trigger input events
2. **Never `.click()` on `button[matsteppernext]`** — use JS `evaluate`
3. **Never loop the same failure.** If an approach fails 3 times, try a different selector, a different interaction pattern, or a different tool.
4. **Don't exhaust the tool budget on a single stuck step.** If you've used >10 tool calls on one element without progress, pause, screenshot, and reassess.
5. **"Add ticket" is a `mat-card`, not a `button`**
6. **Delay options are `cdk-option` cards** — not radio buttons or `mat-option`
7. **Strict mode violations** — use `.first` or `.filter(has_text=...)`
8. **Viewport overflow** — stepper buttons can render at negative coordinates
9. **The travel-date field is `readonly`** — it's a `mat-datepicker-input`. Do NOT `.fill()` or `.click()` it. Use the calendar click pattern or pre-select from Account Summary.
10. **Playwright `fill()` does not work on Angular `mat-datepicker-input`** — it is `readonly` by design. The only reliable fill-style approach is setting `input.value` via `page.evaluate()` then dispatching an `Event('input', {bubbles:true})`.

### Ticket Entry / Upload and Confirm
After selecting duration, the ticket form shows two possible paths depending on ticket type:

**Option A: Image Upload (for paper tickets with QR codes)**
```python
await page.locator('input[type="file"][accept*="image/jpeg"]').first.set_input_files("/path/to/ticket.jpeg")
await page.wait_for_timeout(3000)
await page.locator('button').filter(has_text="Confirm").first.click()
```
The system auto-extracts ticket reference and price from the image.

**Option B: Manual Reference Entry (for e-tickets — no image upload needed)**
SWR allows entering the e-ticket reference number directly. This is the **preferred approach** when you have an e-ticket (e.g. reference `TTBQ7D9FEQF`), because:
- No file upload required (avoids Angular stepper hidden-panel visibility issues)
- SWR calculates compensation automatically from journey + ticket type
- Faster and more reliable than image OCR

```python
# Find the reference input in the active ticket panel
ref_input = page.locator(".cdk-step-content-active input[type='text']").first
if await ref_input.is_visible():
    await ref_input.scroll_into_view_if_needed()
    await ref_input.fill("TTBQ7D9FEQF")  # e-ticket reference
    await ref_input.dispatch_event("input")
    await ref_input.dispatch_event("change")
else:
    # Fallback: brute-force visible text inputs in the ticket form
    for inp in await page.locator('input[type="text"]:visible').all():
        await inp.scroll_into_view_if_needed()
        await inp.fill("TTBQ7D9FEQF")
        await inp.dispatch_event("input")
        await inp.dispatch_event("change")
        break
await page.wait_for_timeout(2000)
await page.locator('button').filter(has_text="Confirm").first.click()
```

**Default preference:** Use e-ticket reference entry by default. Do NOT attempt image upload unless explicitly asked. The reference number is on the e-ticket; no cost/price needs to be entered.

**Adding Ticket 2:** After Ticket 1 confirmed, the `mat-card[aria-label="Add ticket"]` reappears. Repeat the same flow — E-ticket → Return → Reference entry → Confirm.

### Compensation Tab
Navigate via `button[matsteppernext]` with text "Compensation". BACS is pre-populated with saved bank details (sort code / account). Explicitly click the BACS card to confirm selection:

```python
await page.evaluate("""
    () => {
        const cards = document.querySelectorAll('mat-card, [class*="card"]');
        for (const c of cards) {
            if (c.textContent.includes('BACS') && c.offsetHeight > 0) { c.click(); return; }
        }
    }
""")
```

Other options: Card (Visa/Mastercard), Donate to Charity. Expected compensation = 50% of cheapest applicable return fare.

### Review and Submit
Navigate via "Review" in `button[matsteppernext]`. The review page shows a full summary: personal details, journey (with all stops), both tickets (ref + price + uploaded images), and compensation method.

**Key Angular Material interaction pattern:** When Playwright's standard `.click()` fails on Angular Material components (`mat-radio-button`, `mat-card[aria-label="Add ticket"]`, etc.), use `force=True`:
```python
await page.locator('mat-radio-button').filter(has_text="No").first.click(force=True)
```
This bypasses Playwright's visibility/stability checks that Angular's transition animations and wrapper components break.

```python
await page.evaluate("() => { const b = [...document.querySelectorAll('button[matsteppernext]')].find(x => x.textContent.includes('Review')); if(b) b.click(); }")
await page.wait_for_timeout(5000)

# Verify review content, then submit
submit_btn = page.locator('button').filter(has_text="Submit claim")
await submit_btn.click()
await page.wait_for_timeout(10000)

# Check confirmation
url = page.url  # Should be /en/claim-confirmation
```

**Confirmation page:** URL redirects to `/en/claim-confirmation`. Shows:
- "Your claim has been submitted"
- Claim reference (e.g. "SWR-3318-231-542")
- "We aim to respond within an average of 10 days"
- Email confirmation sent automatically

### Complete Working Script Status

A script that automates the full SWR claim pipeline from login through Review is available. See `scripts/swr_claim_complete.py` for the implementation.

**Critical correction:** The Angular stepper file-upload problem is a **red herring**. Do NOT attempt to solve it, do NOT pause for manual upload. The correct approach is:
1. Select **E-ticket/M-ticket** as the type (`force=True` click on `mat-radio-button`)
2. Select **Return** (standard `.click()`)
3. **Enter the e-ticket reference number** directly in the text field that appears
4. Click **Confirm**

SWR calculates compensation automatically from the journey + ticket type. No price/cost required. No image upload required. The reference is on the e-ticket.

**Deprecated:** The `swr-upload-angular-stepper.md` notes about file upload via Playwright are obsolete. The upload path should not be attempted.

**Corrected script:** `templates/swr-claim-complete-v2.py` uses CDP connection, stable `#mat-input-*` selectors, `force=True` Angular clicks, and `--submit` flag.

**Walkthrough reference:** `references/swr-cdp-rewrite-may2026.md` documents the live VNC session corrections.

---

## Adding Stations

Edit `config/stations.json` to add new aliases. Format:
```json
{
  "aliases": {
    "my station": {"crs": "XXX", "name": "Full Station Name"}
  }
}
```

---

## Pricing Sources

**MyTrainPal** (via anti-detection browser): Primary pricing source. No CAPTCHA, loads cleanly. URL pattern: `mytrainpal.com/train-journey/{from}-to-{to}`.

**National Rail**: Cross-validation source. URL pattern: `nationalrail.co.uk/journey-planner/?...`.

**Trainline**: Deep-links are unreliable (bot detection + geo-blocking). Do not use as primary source. MyTrainPal is the replacement.

---

## Dependencies

- `zeep` (SOAP client for OpenLDBWS) — install in your Python environment
- `requests` (for browser automation)
- Python 3.11+
- No external API keys beyond the embedded Darwin token
- Anti-detection browser (for pricing scraping)