# Amazon Returns — Carrier Fallback Strategy (May 2026 Session)

## Session
BrosTrend AX900 Mini Linux WiFi Dongle return, Order 203-0317442-4612374, May 23 2026.

## Problem
Default carrier (Post Office — no box or label needed) selected, but "Confirm your return" button stayed disabled or the form wouldn't advance. The return stalled at the carrier selection page.

## the user's correction
> "if Post Office - No box or label needed doesn't expose the button (I can see it doesn't) then there is also Evri, which YOU SHOULD HAVE CODED in your fallback chain."

> "you ... aren't even bothering to try and be helpful because why wouldn't you have bothered to give me the state of the other buttons if the default is having an issue."

## Solution: automatic carrier fallback chain

When the default carrier stalls the form or does not unlock the Confirm button, iterate through visible carrier options **automatically** before giving up or asking the user.

### Fallback order for automation
1. **Evri Drop Off** ("Evri Drop off – No box or label needed")
2. **ASDA Store** ("ASDA Store - no box or label needed")
3. **Post Office / Royal Mail** ("Post Office/ Royal Mail Drop off – Box required")
4. **Royal Mail** ("Royal Mail Pickup")
5. **Post Office** + branch chooser (only if none of the above work)

### Why this order matters
- **Evri** and **ASDA** do NOT require a drop-off branch selection step. The form submits directly without a modal or postcode search. Playwright automation can click the actual `<input type="submit">` behind the button and advance to `/returns/confirmation/`.
- **Post Office** and **Royal Mail** branch choosers require a modal interaction (postcode search → branch list → "Dropoff here"). This is harder to automate and frequently disables the Confirm button until a branch is chosen.
- The **"2 OTHER RETURN OPTIONS"** expander may need to be clicked first if simpler carriers are hidden.

### What to report
When reaching the carrier page, always extract and report the state of **all visible carrier options**, not just the default:

```python
options = page.evaluate("""
    () => {
        var spans = document.querySelectorAll('span');
        var results = [];
        for (let s of spans) {
            var text = s.innerText?.trim();
            if (text && text.includes('No box') || text.includes('Drop off') || text.includes('Store') || text.includes('Pickup')) {
                results.push(text.slice(0,80));
            }
        }
        return [...new Set(results)];
    }
""")
```

### Code pattern: selecting a carrier and attempting confirm

```python
# Get all visible radio text labels
radios = page.evaluate("""
    () => {
        var r = document.querySelectorAll('input[type="radio"]');
        var out = [];
        for (let el of r) {
            var rect = el.getBoundingClientRect();
            if (rect.y > 200) {  // skip header nav radios
                var container = el.closest('div, li');
                out.push({
                    checked: el.checked,
                    y: Math.round(rect.top + rect.height/2),
                    text: container?.innerText?.slice(0,80) || ''
                });
            }
        }
        return out;
    }
""")

# Try Evri first (no branch selection needed)
for radio in radios:
    if 'evri' in radio['text'].lower():
        page.mouse.click(250, radio['y'])  # click at radio center
        page.wait_for_timeout(2000)
        break

# Click the actual submit input behind the AUI span
submit = page.locator('input[type="submit"]').first
submit.evaluate("el => el.click()")
page.wait_for_timeout(3000)

if "returns/confirmation" in page.url:
    print("Return confirmed successfully")
```

## Outcome of May 2026 session
- Evri Drop Off was selected via `page.mouse.click()` on the text span at y≈740
- The actual `<input type="submit">` behind "Confirm your return" was clicked via Playwright `.evaluate("el => el.click()")`
- Page navigated from `/returns/contract/` → `/returns/confirmation/` successfully
- Amazon sent confirmation email with QR code

## Key lesson
The "Confirm your return" button is NOT an absolute automation boundary. It is **conditional on carrier choice**. Carriers requiring branch selection (Post Office modal, Royal Mail postcode chooser) create a validation gate that prevents automated confirmation. Simple carriers (Evri, ASDA) do not have this gate.

**Rule:** Always try simple carriers first. Only surface to the user after exhausting all visible carrier options.