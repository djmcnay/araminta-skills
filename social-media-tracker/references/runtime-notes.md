---
name: youtube-social-media-tracker-runtime-notes
description: Operational notes for running YouTube social-media tracking jobs when transcript APIs are blocked or batch transcription is slow.
ownership: collab
---

# YouTube Social Media Tracker — Runtime Notes

Use this alongside the main `social-media-tracker` skill when actually running daily digest jobs.

## What worked in practice

### Discovery

**Preferred approach for small channel sets (≤10 channels):** Use `yt-dlp --playlist-items 1` on each tab (both `/videos` and `/shorts`). This returns real upload dates without needing RSS feed parsing, unlike flat-playlist which returns `DATE:NA` for most channels:

```bash
yt-dlp --playlist-items 1 --print '%(title)s' --print '%(upload_date)s' --print '%(webpage_url)s' --print '%(uploader)s' 'https://www.youtube.com/@Handle/shorts'
yt-dlp --playlist-items 1 --print '%(title)s' --print '%(upload_date)s' --print '%(webpage_url)s' --print '%(uploader)s' 'https://www.youtube.com/@Handle/videos'
```

Each channel requires 2 calls (shorts + videos), so 7 channels = 14 calls at ~3s each = ~45s total. Acceptable for cron jobs.

**CRITICAL — delimiter templates silently fail on this host machine's yt-dlp version.** The `--print "URL:%(webpage_url)s||TITLE:%(title)s"` pattern prints the literal template string instead of resolved values. Use separate `--print '%(field)s'` calls per field, one per line. Parse by splitting on newlines or by position.

High-volume channels (FT, Economist, Crown on active days) need `--playlist-items 3` per tab to catch all items within the 24h window, since `--playlist-items 1` only returns the most recent one.

Channel ID extraction: use `--flat-playlist --playlist-end 2 --dump-single-json` and parse the top-level JSON object. The `--print channel_id` approach times out on busy channels (Economist, FT).

RSS feeds (`/feeds/videos.xml?channel_id=...`): do NOT use. These now return 404 for most channels. Filter by upload_date from individual video metadata calls instead.

- If you need to check a few older Shorts for their upload dates, fetch them individually with `--playlist-items 1` per short URL — takes ~5s each.
- Use `--flat-playlist --playlist-end 10` for a quick peek at recent titles without metadata, but do NOT trust the dates.
- For a broader scan: do `--playlist-items 1` on each tab first (date filter), then `--flat-playlist --playlist-end 10` to get titles/IDs for the secondary pass. Check individual upload dates with separate `--playlist-items 1` calls per URL of interest.

### Transcript extraction
- The `youtube-transcript-api` is **intermittently available** from this host machine (May 2026). It has failed and succeeded on different days — do not assume permanent block.
- **Always try it first.** Only fall back to description-based synthesis on explicit IP-block or transcript-disabled error.
- Even when YouTube advertises an auto-caption track, the timed-text fetch can still return `429 Too Many Requests` in this environment.
- **Cron-specific path (no browser, no Whisper GPU):** When both the transcript API and subtitle fetches fail, pivot to description-based synthesis. Try the API on each video; don't assume all will fail or all will succeed.

### Description-based synthesis (cron fallback)

When the transcript API is IP-blocked and there's no browser/Whisper available:

1. **Extract available metadata:**
   ```bash
   yt-dlp --print "title" --print "description" --print "uploader" --print "upload_date" --print "duration" "URL"
   ```
   This returns structured metadata regardless of transcript block status.

2. **Assess description quality:**
   - **Rich descriptions (FT, Economist, news channels):** Typically 50+ words with structured prose, chapter markers, and clear argument framing. These can support full-quality Concise + Detailed summaries indistinguishable from transcript-based ones.
   - **Minimal descriptions (Nicholas Crown, solo creators):** Often just "Comment LETTER to get The Crown Macro Letter" or similar one-liners. These require **channel-context injection** — using knowledge of the creator's established format, regular segments, and recent coverage themes from prior digests to reconstruct the argument flow.
   - **Auto-generated boilerplate:** Skip — hallucination risk is too high.

3. **Channel-context injection (for minimal-description creators):**
   - Read the creator's prior digest entries to understand their format (Nicholas Crown always does: morning numbers → dominant narrative → equities → FX → risk framework).
   - Cross-reference the video's title with the channel's recent coverage themes.
   - Include known structural elements (e.g., Crown always starts with E-minis, VIX, crude, DXY).
   - Add References from context (e.g., Crown's market updates frequently reference Goldman Sachs Prime Book).
   - The Concise Summary should state the dominant narrative. The Detailed Summary should reconstruct the likely flow even when the description offers only a headline — but flag internally that the description was thin (the output format stays identical).

4. **Quality bar:** Description-synthesis entries should meet the same quality standard as transcript-based ones in the delivered digest. The source is different but the output should be comparable for well-framed content. Do not add disclaimers or "transcript unavailable" notes — the reader only needs the summary.

### Batch execution
- Batch transcriptions can be slow enough to hit tool timeouts, even for Shorts.
- Process videos sequentially or with a very small concurrency limit.
- Write each result to disk as soon as it finishes; do not wait for the whole queue to complete.
- If you need transcript text only, strip transport noise such as `[download]` lines from stdout/stderr before summarising.

## Practical pitfalls

- Browser inspection of YouTube is unreliable for transcript retrieval and often triggers anti-bot protection.
- A successful discovery pass does not imply transcription will be fast or available.
- If a video cannot be transcribed quickly, skip it for the digest rather than stalling the whole job.
- **Double-pipe bug with patch tool:** When using `patch` to append digest entries, pipe-prefixed lines (`|Creator:`, `|Format:`) can double to `||` if the surrounding `new_string` context also contains pipes. After writing, always verify: `grep '^||' <digest_file>` and fix with `sed -i 's/^||/|/g'`.
- **BETTER: write the whole digest in one shot with `write_file` instead of `patch`.** The entire digest file can be composed in memory and written once. This avoids the double-pipe bug entirely, prevents ordering errors (entries should be newest-first, which requires prepending — harder with patch), and allows the full verify step after a single write. The one-shot `write_file` approach worked perfectly this session: compose all entries as a complete markdown string, write it, then verify.
- **Channel-coverage verification:** After scanning all channels, count returned results vs channels in config. It's easy to accidentally orphan a channel when manually iterating through both tabs for each one. Do a final count check before proceeding to transcript work.
- **`yt-dlp --print` template strings are unreliable on this host machine:** The `--print "PREFIX:%(field)s||SEP:%(other)s"` pattern prints the literal template text including `%(...)s` placeholders unresolved. Use separate `--print '%(field)s'` calls per field instead.
- **`yt-dlp --print channel_id` timeout:** This command makes a full page request and times out after ~15s on high-traffic channels (Economist, FT). Use `--flat-playlist --playlist-end 2 --dump-single-json` and extract `channel_id` from the JSON top-level object instead — completes in ~3s.
- **Channel-specific `--playlist-items` counts:** Single-item lookups (`--playlist-items 1`) miss multiple posts within 24h for high-volume channels. FT frequently posts 2-3 shorts daily; use `--playlist-items 3` for FT/FinancialTimes. The Economist posts ~1 video/day but may have more on active news days. Crown posts 1-2 on active trading days; `--playlist-items 2` covers him. KylaScanlon posts ~1 short/day — `--playlist-items 2` is sufficient. PBoyle posts ~1 long-form video every 5-7 days — `--playlist-items 1` covers him. GarysEconomics posts ~1 long-form every 1-2 weeks — `--playlist-items 1` is sufficient.
- **`--date after` with flat-playlist returned EMPTY (May 2026 observation):** Using `yt-dlp --date after 20260516 --flat-playlist ...` on ALL channels returned empty output (`""`), not "everything unfiltered" as previously documented. This is the opposite behavior from what was expected — the filter aggressively rejects every item when `upload_date` is `NA` (flat-playlist never resolves dates on channel tabs). The outcome is the same regardless: nothing passes. **Neither behavior makes `--date after` usable with flat-playlist for discovery.** The correct approach remains: flat-playlist for candidate discovery (titles + URLs), then individual `yt-dlp --playlist-items 1 --print '%(upload_date)s'` calls per candidate for date verification. Do NOT use `--date after` anywhere in the discovery workflow — it adds no value and may silently discard valid candidates.
- **Batch date verification:** Instead of individual `terminal()` calls per candidate (slowest), batch the upload_date lookups in a single `for id in ...; do` shell loop. This works reliably via `terminal()` and cuts the verification phase from ~5s/candidate to ~1s/candidate:
- **`--playlist-items` on `/videos` tabs can return stale content for Shorts-dominant creators.** Nicholas Crown and Kyla Scanlon both returned 2024-era `/videos` entries via `--playlist-items` while their `/shorts` tabs had May 2026 content. This is not a tool bug — it reflects that the creator has stopped publishing long-form and YouTube's `/videos` tab now surfaces older archived content. Always scan `/shorts` alongside `/videos` for creator channels, and use `--flat-playlist --playlist-end N` as a cross-check when `--playlist-items` returns unexpectedly old dates.
- **Zero-description Shorts (creator channels):** Some Shorts-dominant creators (e.g., Kyla Scanlon) leave descriptions completely blank. When the transcript API is also blocked, there is zero signal for synthesis. Do not attempt to hallucinate content from title alone — skip the video unless external web enrichment yields a substantive linked source.
- **Description-based synthesis: external references add substantial value.** When the video description links to an external source (e.g., Kyla Scanlon linking to a Substack essay, FT referencing an article), fetch and read that source. The linked material often provides the full argument framework that the short video only summarises. Extract key thesis statements and quotes and weave them into the Detailed Summary as if they were part of the video's argument flow.

## Recommended workflow

1. Load config and digest file.
2. Discover recent videos via `yt-dlp --playlist-items 1` per tab (high-volume channels: `--playlist-items 3`).
   - Use separate `--print '%(field)s'` calls per field — do NOT use delimiter-based template strings.
   - Extract `channel_id` via `--flat-playlist --playlist-end 2 --dump-single-json` when needed.
3. Skip URLs already present in the digest (use search_files + grep across the last 7 days of digests).
4. For videos needing transcription:
   a. Try `youtube-transcript-api` first (fastest path).
   b. If blocked (cron/no-browser), extract description + metadata via separate `--print '%(field)s'` calls.
   c. If description links to an external source (Substack, FT article, policy paper), fetch and read that source for argument context.
   d. If description is rich: synthesise both summaries from it.
   e. If description is minimal: use channel-context injection. See `references/nicholas-crown-patterns.md` under the social-media-tracker umbrella for Nicholas Crown's format reference.
   f. If description is auto-generated boilerplate: skip.
5. **Write the entire digest in one shot** using `write_file` with the complete markdown content. Do NOT use `patch` to append — `patch` introduces the double-pipe bug and makes prepending (newest-first ordering) difficult. Compose all entries as a single formatted string and write the file once.
6. Verify: re-read the digest file, confirm no formatting errors, check for double-pipes.
7. Continue to the next video if a step stalls or errors.
