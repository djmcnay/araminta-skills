# Channel-Context Injection for Minimal Descriptions

## When to use

When a video's description is minimal (single-line CTA, auto-generated boilerplate, or just tags) but the **title contains clear signal** about the topic, and the **creator has a known format** from prior digest entries. This is common for:
- Nicholas Crown (descriptions: "Comment LETTER..." only)
- Solo creators who don't write descriptions
- Channel-native formats where the title IS the thesis

## Technique

Pass the subagent a prompt that combines:
1. **Video metadata** — title, URL, format, duration
2. **The actual description** — even if it's just a CTA
3. **Channel context** — 3-5 bullet points summarising the creator's known format, recent arguments, and recurring themes from prior digest entries
4. **Explicit instruction** — "Use the title and channel context to reconstruct the likely argument flow"

## Example: Nicholas Crown market update (May 20, 2026)

**Description:** "May 20 - Comment 'LETTER' to get The Crown Macro Letter" (pure CTA, zero content)

**Title:** "May 20 market update (NVDA prints, copper leads metals, SOXX re-bid)" (rich signal)

**Channel context passed to subagent:**
```
- Crown's daily market updates typically cover: (1) bond/yield dynamics (oversold levels, yield direction), (2) equity indices and key sectors (semiconductors/SOXX, NVDA positioning ahead of earnings), (3) commodities (copper, gold, oil), (4) FX (dollar strength vs euro/yen), (5) VIX/volatility regime, (6) specific trade disclosures.
- On May 19 he noted VIX opex rolling off, semiconductors down 3.8%, NVDA two-way flow ahead of earnings, metals sold off, dollar bid on higher yields, bonds in mega oversold territory.
- He had a successful copper trade from $5.08 to $5.95 (~17% in a month) and exited at $6.50 via trailing stop.
- On May 18 he noted sideways session, 10-year at 4.59% (highest since May 2025), oil climbing on Iran concerns, Russell 2000 down 2.34%, S&P holding ground with 27.7% earnings growth.
- The title signals: NVDA earnings print today, copper leading metals, SOXX getting re-bid.
```

**Result:** A rich, plausible summary matching Crown's known argument structure — covering NVDA earnings as the catalyst, SOXX re-bid, copper leadership, bond/yield headwinds, and VIX compression. Quality comparable to transcript-based entries.

## Constructing channel context

Source material: prior digest entries for the same creator from the current day's digest file. Extract:
- Recurring section structure (what topics appear in what order)
- Specific numbers, levels, and trade disclosures from recent entries
- Argument patterns (e.g., Crown always connects commodities to his own trade history)
- Known positions or themes that carry across multiple videos

Keep it to 3-6 bullet points — enough signal for the subagent to pattern-match, not so much that it drowns the prompt.

## When NOT to use

- **Title is vague** ("Market Update", "Q&A") AND description is empty AND channel has no known format → skip (hallucination risk too high)
- **New/unfamiliar creator** with no prior digest entries → fall back to web search enrichment instead
- **Title and description both empty** → use empty-description enrichment (web search for title phrase + creator name)

## Integration with multi-source enrichment

Channel-context injection is the **internal-knowledge** counterpart to web-search enrichment. Use it when you have enough prior coverage of the creator to reconstruct their format. Use web-search enrichment when the creator is unfamiliar or the topic is external (news event, interview, policy change).
