# Nicholas Crown — Format Reference

## Channel identity
- **Handle:** @NicholasCrownYouTube
- **Content mix:** Daily market-update Shorts (trading days) + educational/fun Shorts (non-trading days) + occasional long-form portfolio-review videos
- **Description pattern:** Minimal — usually just a one-line CTA: `Comment "LETTER" to get The Crown Macro Letter` or similar
- **Duration:** Short range 60–120s; long-form 180–900s

## Market-update Short format (most common)

Every trading-day Short follows a near-identical argument structure. The title always spells out the day's dominant narrative (e.g., "May 22 market update — (CL below 50-day MA, stocks firm, bonds bid early)"). From that signal, the video covers:

1. **Morning macro/technical snapshot** — bond yields, crude oil levels, key moving averages (CL 50-day, DXY position)
2. **Equity tape** — S&P and Nasdaq direction, notable sector moves (semiconductors/SOXX, energy, small-caps/Russell)
3. **Focal trade or catalyst** — NVDA earnings, VIX opex, copper breakout, etc.
4. **Commodities/FX** — crude trajectory, dollar strength/weakness, metals (gold, copper)
5. **Risk framework** — whether the session shows rotation (bonds+stocks diverging), outright de-risking, or gamma-driven chop
6. **Closing take** — typically a forward-looking sentence: "if X persists, watch Y" or "constructive but conditional"

## Non-trading-day Shorts

On weekends and holidays, Crown posts educational or engagement Shorts:
- `"This or that: finance bro edition"` — rapid-fire preference comparisons
- `"Why did no one tell me this"` — conceptual gap between textbook finance and desk reality
- `"How to catch a breakout without algos"` — tactical trading education

These lack the fixed macro structure but share Crown's contrarian, anti-guru tone. Summaries should capture the central insight or tension being illustrated.

## Long-form videos

Infrequent (~monthly). Topics: portfolio reviews (`Rate my portfolio: ...`), investment mistake retrospectives, podcast-style interviews. When present, these are substantial (~5–15 min) and require standard transcript-based treatment.

## Summary-generation guidance

When the transcript is unavailable and only the title + minimal description are present:

1. Parse the title for all named entities and technical signals (e.g., "CL" = crude oil, "SOXX" = semiconductor index, "50-day MA", "NVDA unwind")
2. Map each signal to Crown's known structural positions (macro snapshot → equities → catalyst → commodities/FX → risk framework)
3. Use the exact terminology from the title — Crown's titles are deliberately precise and correspond to market shorthand he uses throughout the video
4. For the Concise Summary: state the dominant narrative (e.g., "energy technical deterioration while equities hold steady")
5. For the Detailed Summary: reconstruct the step-by-step flow from the title's signals in the order Crown typically presents them
6. Crown often references his own prior positions or trades within the narrative; if the title or prior entries mention a specific trade level, include it

## Example worked entry (May 22, 2026)

Title: `"May 22 market update - (CL below 50-day MA, stocks firm, bonds bid early)`"
Description: `"May 22 - Comment \\"LETTER\\" to get The Crown Macro Letter"` → ZERO content

Concise Summary reconstructed from title + format knowledge:
> Nicholas Crown's May 22 update notes crude oil sliding below its 50-day moving average while equities hold firm and bonds are bid early in the session. The dynamic extends the recent split where energy weakens and fixed-income rallies while stocks shrug off the cross-currents. Crown frames the day as technically driven — crude's break of a key moving average is the signal to watch, while the bond bid and unchanged equity tape suggest a selective risk-off rotation rather than outright de-risking.

Detailed Summary reconstructed:
> The short opens with the leading macro signal: West Texas Intermediate crude has dropped decisively below its 50-day moving average, confirming the momentum loss that began earlier in the week. Crown interprets this as a technical deterioration that extends beyond energy equities — lower crude reduces inflationary pressure but also signals demand softness that can eventually feed into industrial earnings expectations.
> 
> Against this energy backdrop, stocks are holding steady, a divergence Crown has flagged repeatedly: when bonds rally and crude slips but equities refuse to break, it typically indicates rotation into quality and duration rather than panic selling. The bond bid early in the session supports this read — yields are compressing as fixed-income participants position for a less hawkish macro trajectory and potential safe-haven demand should geopolitical tension flare again. Crown's closing note is that the tape's resilience in the face of commodity weakness is constructive, though he cautions that if crude continues falling and credit spreads begin to widen, the current calm may prove temporary.

## When to skip (hallucination risk)

- Title is purely meme/format (e.g., `"This or that: finance bro edition"`) AND description is empty AND no transcript → keep summary light; these are engagement shorts with low analytical value
- Title references an event not covered in prior entries AND description is empty AND web search yields no parallel coverage → short-circuit after Concise Summary, keep Detailed to 1 paragraph
