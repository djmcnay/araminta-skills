# Channel Coverage Patterns

Empirical coverage data for each tracked channel, collected during daily digest runs. Use this to tune `--playlist-items N` counts and expected daily volume.

## Pattern summary

| Channel | Videos/Shorts per 24h | `--playlist-items` needed | Tab priority | Notes |
|---------|----------------------|--------------------------|--------------|-------|
| @KylaScanlon | 0-1 Short | 1 | Shorts only | Rarely posts long-form; most content is ~60s analysis shorts |
| @NicholasCrownYouTube | 1-4 Shorts + occasional Long-form | 3 | Shorts + Videos | **Expanding format.** Previously only trading-day market updates; now posting **educational shorts and long-form reflection videos** too (positioning data, trader mindset, worst-investment-mistake recaps). May 18, 2026: posted a **long-form video** ("Worst Investment Mistakes in 2025", 547s) from the `/videos` tab on a Monday. **Check both tabs every day** including weekends and holidays — do not assume trading-day-only posting. |
| @PBoyle | < 1/week | 1 | Videos > Shorts | Low-volume; check weekly not daily |
| @garyseconomics | < 1/week | 1 | Videos > Shorts | Low-volume; check weekly not daily |
| @TheEconomist | 1-3 items | 3 | Shorts + Videos | Posts both a weekly long-form (~1/week) and several shorts (~1-2/day). Long-form often has full chapter markers in description. |
| @FinancialTimes | 2-5 Shorts + 0-1 Long-form | 5 (shorts) + 2 (videos) | Shorts > Videos | Highest-volume channel. Posts multiple shorts on different topics daily. Long-form videos (FT Film series) are ~30min documentary style every 5-7 days. The long-form video's description is rich (chapter markers, full synopsis) and transcript **may** be available — always try fetch first. **Always use `--playlist-items 5` on shorts.** |
| @nateherk | 1-2 Long-form + occasional Shorts | 2 (videos) + 1 (shorts) | Videos + Shorts | Long-form content with detailed descriptions including chapter timestamps. Shorts are less frequent. |

## Empirical observations (May 2026)

### Financial Times (highest volume)
- **May 8, 2026:** 4 shorts posted in 24h (Ceasefire/Hormuz, Sotheby's, UK local elections, UBS/Ermotti)
- **Tab:** Almost exclusively `/shorts`
- **Description quality:** Rich 20-40 word summaries that are transcript-equivalent for digest purposes
- **Best practice:** `--playlist-items 4` on `/shorts` tab

### The Economist
- **May 7-8, 2026:** Posted 1 long-form (Rahm Emanuel interview) + 3 shorts on the same topic (Emanuel: AI, nomination prospects, Netanyahu)
- **May 17-18, 2026:** Interview with EU Trade Commissioner Maroš Šefčovič on EU-China trade appeared under video ID `10u4734jN9Q` on May 17, then was **republished under `UQG6rdeFIcM`** on May 18. The old URL went dead (yt-dlp returns empty output, exit code 1) while the new URL has identical content. This is not a duplicate — it's the same video re-uploaded, likely due to an edit or re-release.
- **Republish signal:** Same channel, same title, new URL within 24h, old URL returns empty from yt-dlp. When detected, update the existing digest entry's `Link:` field rather than adding a new entry.
- **Tab mix:** Long-form on `/videos`, shorts on `/shorts` — both tabs need scanning independently
- **Description quality:** Long-form descriptions are excellent — full article summaries with chapter timestamps. Short descriptions are brief (15-25 words) but pack the thesis into one sentence.
- **Best practice:** `--playlist-items 3` on both `/videos` and `/shorts`

### Nicholas Crown
- **May 13-15, 2026:** Posted 5 shorts in 3 days — 3 market updates (May 14 AM, May 14 PM, May 15 OPEX) + 2 educational pieces ("You don't need to be a trader to be a trader", "What I wish I knew when I started trading")
- **Expanding format:** Previously only market updates on trading days. Now adding educational content about positioning/process/trading mindset. Check daily, check `--playlist-items 3`.
- **Description quality:** Minimal (typically "Comment LETTER..." only). **Must use channel-context injection** — reconstruct flow from title + known format + prior digests.

### Nate Herk
- **May 7-8, 2026:** Posted 2 long-form videos (May 7: session limits, May 8: AI tech stack tier list)
- **Description quality:** Excellent — full chapter timestamps with descriptive headings, detailed paragraphs explaining each section
- **Best practice:** `--playlist-items 2` on `/videos`, `--playlist-items 1` on `/shorts`

### No-content channels
- @PBoyle: Last video May 2, 2026 (Is Inflation About to Get Much Worse?)
- @garyseconomics: Last video May 3, 2026 (Who should you vote for?)
- These channels can be checked with `--playlist-items 1` once rather than scanning both tabs; if the most recent item is >7 days old, mark as no-content and move on.
