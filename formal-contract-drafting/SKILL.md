---
name: formal-contract-drafting
description: Draft clean, fully populated formal agreements from scratch when template editing has produced artefacts or the user wants a lender-facing / signable contract.
ownership: collab
version: 1.1.0
author: Araminta
license: MIT
tags: [contracts, legal-documents, markdown, pdf, html]
category: productivity
---

# formal-contract-drafting

Use this when drafting a tenancy agreement, side letter, underwriter-facing contract, or similar formal document where the user wants a clean final agreement rather than a visibly edited template.

## When to use

Trigger when any of the following are true:
- The user wants a contract or agreement that is **fully populated except signatures/dates**.
- Existing ODT/DOCX/template files contain guidance notes, checkboxes, prompts, or half-removed boilerplate.
- The user complains that a draft "looks stupid", contains template debris, or is not fit to send.
- A lender / solicitor / counterparty will read the document, so presentation matters.
- The user asks for markdown first, then PDF / Word-friendly output.

## Core rule

**Do not try to salvage a bad form by search-and-replace if the visible output has already become messy.**

If the template has leaked guidance text, checkboxes, XML cruft, or unpopulated placeholders into the rendered document, abandon that route and draft afresh.

Use the government / standard form only as the **legal spine**, not as a formatting substrate.

## Workflow

1. **Extract only the agreed commercial facts**
   - Parties
   - Property / subject matter
   - Start date and conditionality
   - Term and rollover mechanics
   - Rent / price / review clause
   - Deposit / inventory position
   - Special permissions (alterations, subletting, lodgers, etc.)
   - Notices details
   - Any special options (for example a RICS valuation purchase option)

2. **Resolve material ambiguities before drafting**
   Ask only for points that genuinely alter the document, such as:
   - service address / email
   - legal names
   - commencement condition wording
   - whether special permissions are standing consent or conditional consent

3. **Draft from scratch in Markdown first**
   - Keep only signature lines and signature dates blank unless the user asks otherwise.
   - No checkboxes, crosses, prompts, editor notes, or "insert here" text.
   - Use a proper cover page for formal agreements unless the user says not to.
   - Use numbered clauses and short headings.
   - If the user asked for a standard AST, use the government AST / Housing Act structure as the clause backbone, but rewrite cleanly.

4. **Add practical, responsibility-preserving language where permissions are broad**
   Example: if lodgers / subletting / occupiers are permitted, expressly state that the tenant remains responsible for the condition of the property and for any damage, nuisance, or breach caused by those people.

5. **Produce delivery formats**
   Save in the working project / vault folder as:
   - `.md` — source of truth / easiest to revise
   - `.html` — styled execution copy
   - `.rtf` — Word / Google Docs friendly fallback when DOCX tooling is unavailable
   - `.pdf` — generated from HTML where possible

6. **Generate PDF from HTML with headless Chromium**
   Preferred command:
   ```bash
   chromium --headless --disable-gpu --no-sandbox \
     --print-to-pdf='/absolute/path/output.pdf' \
     'file:///absolute/path/input.html'
   ```
   Notes:
   - Chromium may emit noisy flag warnings but still produce the PDF successfully.
   - Verify the output file exists rather than panicking at stderr chatter.

7. **Surface the final file back to the user**
   - Give the file paths.
   - Attach / surface the PDF in chat if possible.
   - Briefly list material drafting changes.

## Drafting conventions

- Tone: plain, formal, lender-readable.
- Prefer "where lawful" around statutory possession wording rather than pretending the contract can override statute.
- If commencement is conditional on approval / consent, say so expressly and state what happens if approval is not in place by the intended start date.
- If notices may be served by email, include both physical service address and email address.
- Avoid decorative legalese. Clean beats theatrical.

## Recommended structure for AST-style agreements

1. Cover page
2. Parties
3. Property
4. Tenancy type
5. Term
6. Rent
7. Rent review
8. Deposit / inventory
9. Use / occupation / subletting / lodgers
10. Alterations
11. Special options / side rights
12. Landlord obligations
13. Tenant obligations
14. Ending the tenancy
15. Notices
16. General
17. Signatures

## Pitfalls

- Do not trust a visually broken ODT just because the text content is technically present.
- Do not leave old assumptions in place after the user changes key terms (for example 6 months becoming 12 months).
- Do not promise DOCX if the required library / office tooling is not installed; use RTF as the reliable editable fallback.
- Do not omit a cover page if the document is meant to look like a proper agreement pack.
- Do not leave service-of-notice mechanics vague when the user has specified email service.

## Verification checklist

Before finishing, confirm:
- Only signatures and intended dates remain blank.
- No guidance notes / prompts / checkboxes remain.
- The current agreed commercial terms replaced any stale earlier version.
- The PDF was actually generated.
- Files are saved in the project folder, not stranded elsewhere.