# Financial Times Channel — Operational Notes

## Channel characteristics
- **Handle:** @FinancialTimes
- **Posting frequency:** 2-3 shorts/day + 1 long-form every 3-5 days
- **Primary content:** News analysis, interviews, FT Films (documentary mini-series)
- **Transcript availability:** Unpredictable. Long-form videos return "Transcripts disabled" reliably. Shorts **may** return usable transcripts — the API is intermittently available for Shorts even when blocked for long-form. Always try `fetch_transcript.py` first regardless.

## Scan parameters
- **`--playlist-items 3`** for both `/shorts` and `/videos` tabs (2-3 posts per day, `--playlist-items 1` misses recent items)
- **Timeout risk:** The `/videos` tab regularly times out after 30-60s. Mitigation: run the videos scan before shorts, with a 90s timeout. If it times out, retry once with `--playlist-end 5` instead of full playlist.
- **Short URLs** in the `/shorts` tab — FT prepends `#shorts` to their video titles

## Transcript strategy
1. Try `fetch_transcript.py` first — Shorts sometimes work even when long-form doesn't.
2. If blocked (expected for long-form): fall back to description synthesis.
3. **Description quality:** FT short descriptions are typically 20-40 words but information-dense — enough for full Concise Summary. Long-form descriptions are 80-150 words with structured prose and chapter markers — enough for both Concise and Detailed.
4. **Transcript API rate-limit pattern (observed May 15, 2026):** The first 8 videos across all channels succeeded, then the next 6 (including all FT shorts after the first batch) returned IP-block errors. FT shorts are hit hardest because they cluster at the end of the scan order. Mitigation: process FT shorts early in the scan loop, or accept that the latter FT shorts will need description-based synthesis. The API is NOT permanently blocked — next session it will work again.
5. **Multi-source enrichment:** FT shorts often cover syndicated news. Search for the same topic across BBC, CNBC, Al Jazeera for the full framework. Cross-reference with the FT article linked in the description when available.

## External references in descriptions
FT video descriptions often link to related FT articles. Fetch these when available — the article provides the full argument framework that the short video summarises. Extract thesis statements and weave them into the Detailed Summary.

## Known scan failures
- `yt-dlp --flat-playlist` on FT videos returns `DATE:NA` for all entries (same as other publishers).
- `--playlist-items N` returns real dates but times out frequently on the videos tab.
- RSS feeds return 404.

## Summary patterns from this channel
FT shorts at 20-40 word description length: each sentence carries informational weight. A 30-word description like "Donald Trump arrived in Beijing on May 13 for his second-ever visit to China. The summit covers trade, Iran, and Taiwan. Trump's top objective is securing China's help resolving the Iran war." is enough for a 3-5 sentence concise summary because it directly states the thesis, the stakes, and the key players. No padding needed.
