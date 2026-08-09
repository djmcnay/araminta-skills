# Parliamentary / voting-record lookup notes

Use this when answering UK local-representation questions (postcode, village, ward, constituency, MP, voting record).

## Reliable lookup order
1. Search the exact postcode or locality name plus `constituency`.
2. Prefer UK Parliament postcode/constituency results when the search snippet gives a direct seat + MP answer.
3. Use a geographic locator such as Find That Postcode when you need a locality-to-constituency mapping and the Parliament site is awkward to extract.
4. Use TheyWorkForYou for concise voting summaries and party-alignment percentages.

## Practical quirks
- Boundary changes matter: for areas around the 2024 review, confirm whether the seat is new, renamed, or cross-county before answering.
- Some Parliament pages are hard to fetch with generic extractors; search snippets may be enough to identify the constituency and MP.
- For voting record questions, the useful signal is often the party-alignment percentage plus the policy-area summary headings, not the full vote-by-vote table.
- If a locality maps to an unexpected seat, mention the locality name and the exact postcode used; nearby villages can fall in different constituencies.

## Example pattern
- Postcode search snippet: `<postcode> -> Farnham and Bordon -> Gregory Stafford (Conservative)`
- Voting summary: `99% aligned with Conservative MPs over the last year`

## What to avoid
- Do not guess the seat from the county name alone.
- Do not rely on stale pre-2024 constituency names without checking boundary changes.
- Do not treat a failed fetch as absence of data; retry via search snippets or another source.
