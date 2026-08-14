# Prepend Discipline — Only Genuinely New Entries

## The trap

When writing the updated digest file, it's tempting to compose the entire file from scratch, including entries for videos that were already in the file from earlier runs or that aren't from today (2026-05-11). This corrupts the digest in two ways:

1. **Placeholder pollution**: Adding entries like "[Content being processed]" for non-today videos inflates the file and buries the genuinely new content.
2. **Duplicate maintenance**: You end up maintaining the full history on every run instead of just the delta.

## The fix

When prepending new entries:

1. Read the **existing digest** in full (no offset/limit).
2. Compose only the **genuinely new entries** (today's upload_date that aren't already present).
3. Prepend those new entries above the existing content.
4. Write the result as a single `write_file`.

Do NOT include:
- Entries that were already in the digest from prior runs (they're already there).
- Placeholder entries for non-today uploads, even if you scanned them.
- Non-today uploads (upload_date != today's date) unless they somehow got missed in a prior run.

## Verification

After writing, spot-check:
- Are new entries at the top (newest first)?
- Are old entries unchanged in the bottom section?
- Is there no duplicate content?

## Example from 2026-05-11

Scanned 7 channels × 2 tabs. Found multiple uploads from May 9, May 10, May 11.
- May 11 uploads: 2 (Crown market update, FT banking short) → prepended to digest.
- May 9/10 uploads: already in digest from prior runs → skipped.
- April uploads: not today → skipped.
Result: only 2 new entries were prepended to the original 7. Clean.
