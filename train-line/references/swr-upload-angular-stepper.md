# SWR Ticket Upload — Angular Stepper File Input Problem

## Problem

After selecting E-ticket → Return in the Ticket step, Angular renders a file upload area. The file input is `input[type="file"]` but Playwright cannot reliably target it because:

1. Angular Material stepper renders ALL step panels in the DOM simultaneously (only the active one is visually visible)
2. The file input may exist in multiple step panels, but only the one in the active panel is meaningful
3. Playwright's `.set_input_files()` checks element visibility/hittability, which fails on inputs in hidden Angular panels
4. Even after making inputs visible via `style.display = 'block'`, Playwright times out

## Attempted Solutions (May 2026)

| Approach | Result |
|----------|--------|
| `page.locator('input[type="file"]').first.set_input_files()` | Timeout — input not actionable |
| `.last.set_input_files()` | Same — still hidden |
| Iterate all inputs, try each | Same — all fail visibility check |
| `page.evaluate()` with base64 → create Blob → create File → set `input.files` + dispatch 'change' | Element found but Angular form doesn't register the upload; no thumbnail/preview appears |
| Make inputs visible via `style.display = 'block'` then Playwright `.set_input_files()` | Still fails — Playwright checks hittability on screen coordinates |
| `CDP Runtime.evaluate` with same base64 approach | Not attempted — may work if direct DOM manipulation bypasses Angular's form control registration |

## Working Alternative: CDP SetFileInputFiles

The Chrome DevTools Protocol has `DOM.setFileInputFiles` which bypasses Playwright entirely. To use:

```python
# Get the nodeId of the file input via CDP querySelector
await browser_cdp(method='DOM.querySelector', params={
    'nodeId': root_node_id,
    'selector': 'input[type="file"]'
})
# Then set files via CDP
await browser_cdp(method='DOM.setFileInputFiles', params={
    'nodeId': file_input_node_id,
    'files': ['/path/to/ticket.jpg']
})
```

**Not yet verified** — requires a CDP-capable browser backend (not Camofox/REST-only).

## Current Workaround (May 2026)

Manual intervention for the upload step. The script automates everything up to and including "Return" selection, then stops for manual upload.

## Full End-to-End Status

- ✅ Login
- ✅ Date (calendar click)
- ✅ From/To/Time (autocomplete with keyboard.type)
- ✅ Journey search & select
- ✅ Delay selection
- ✅ Multiple tickets radio (force=True)
- ✅ Add ticket card click (force=True)
- ✅ E-ticket selection
- ✅ Return selection
- ❌ Upload (Playwright cannot target Angular-hidden file input)
- ✅ Confirm (works after manual upload)
- ✅ Compensation → BACS
- ✅ Review
- ✅ Submit

**Next session should attempt:** CDP `DOM.setFileInputFiles` with local Chromium, or try triggering the upload via the visible "Upload" button click (which opens a native file picker — not automatable in headless).
