---
name: youtube-social-media-tracking-digest-workflow
description: Daily workflow for scanning YouTube channels, filtering recent uploads, deduplicating against a digest, extracting transcripts, and prepending structured entries.
ownership: collab
---

# YouTube Social Media Tracking — Digest Workflow

Use this for cron-style jobs that scan YouTube channels, find recent uploads, and write a daily digest with summaries.

## When to use
- You need to monitor a configured set of YouTube channels on a schedule.
- You must scan both `/videos` and `/shorts` tabs.
- You need to filter to uploads from the last 24 hours.
- You need to skip URLs already present in the daily digest.
- You need to produce short and detailed summaries from the video transcript.

## Workflow

### 1. Load inputs
   - Read the channel list from the tracker config JSON.
   - Read the current daily digest file for the active date.
   - Use absolute paths throughout.

### 2. Discover recent uploads

**Rolling date range for "last 24 hours" is mandatory.** Do NOT hardcode a single date string. Compute both today and yesterday:

```bash
TODAY=$(date +%Y%m%d)
YESTERDAY=$(date -d '-1 day' +%Y%m%d)
```

Then filter `upload_date` against both: `if [ "$upload_date" = "$TODAY" ] || [ "$upload_date" = "$YESTERDAY" ]`. This catches uploads from late the previous day that are still within the last 24 hours. The daily digest file is named for the run date (e.g. `2026-05-18`), but the data you're looking for spans both days.

**Concrete failure pattern (May 18, 2026):** Nicholas Crown posted "Worst Investment Mistakes in 2025" on 2026-05-18 (upload_date `20250518`). Because the digest filename was for the 18th but the filter checked only `20260517`, this video was missed entirely. The correct filter would have caught both `20260517` and `20260518`. After running the scan, verify count against the channel's known posting frequency.

**Primary method (sequential shell loop — preferred for ≤10 channels):**

For ≤10 channels, a single sequential shell loop is faster and more reliable than subagent dispatch parallelism. The entire scan (14 yt-dlp calls for 7 channels × 2 tabs) completes in ~2 minutes. No batching overhead, no coverage gaps from orphaned tasks:

```bash
for handle in "ChannelName" "OtherName"; do
  echo "=== @$handle videos ==="
  yt-dlp --playlist-items 1-5 \
    --print '%(webpage_url)s' --print '%(title)s' --print '%(upload_date)s' --print '%(uploader)s' \
    "https://www.youtube.com/@${handle}/videos" 2>/dev/null
  echo "=== @$handle shorts ==="
  yt-dlp --playlist-items 1-5 \
    --print '%(webpage_url)s' --print '%(title)s' --print '%(upload_date)s' --print '%(uploader)s' \
    "https://www.youtube.com/@${handle}/shorts" 2>/dev/null
  echo ""
done
```

**This replaces `subagent dispatch` for standard runs.** Keep subagent dispatch for the rare case of 15+ channels where sequential runtime becomes prohibitive.

**Concurrency limit:** `subagent dispatch` has `max_concurrent_children: 3` hard-capped in config.yaml. For 7 channels × 2 tabs = 14 discovery tasks, you either use the sequential loop or split into 5+ subagent dispatch batches (3 tasks per batch). If you batch, **verify every handle from the config was covered** — orphaned channels at the end of an uneven 3-3-1 batch are the most common miss.

**Immediate-write discipline:** After each summary is generated, write that entry to the digest file immediately. Do NOT batch-write at the end. This session confirmed the pattern: transcript API rate-limits mid-session (first 5-8 videos succeed, then IP-block errors). If you batch-write, a rate-limit at video 5 loses videos 1-4. Each video processed should result in a file modification right then.

**Format detection:** Tab origin is the primary signal. If a video comes from `/shorts`, it is a Short regardless of duration — YouTube now allows Shorts up to 180s. Common examples: Crown's 97s market update, FT's 81s and 122s shorts all appear under `/shorts` and are correctly classified as Shorts.

```bash
yt-dlp --print "%(duration)s" "https://www.youtube.com/watch?v=VIDEO_ID"
```

- Tab origin takes precedence. `/shorts` tab → Short (any duration up to 180s).
- `/videos` tab → Long-form (any duration).
- Only use duration as a tiebreaker when tab origin is ambiguous or the video lacks tab context entirely. In that case: duration < 60s → Short; duration ≥ 60s → Long-form.

**Do NOT use:**
- `--flat-playlist` — returns `DATE:NA` for upload dates with this host machine's yt-dlp version (2026.03.17).
- RSS feeds — `feeds/videos.xml` returns 404 for all channel IDs on this host machine.
- `--dump-single-json` — JS challenge errors block JSON parsing.
- `--date` — silently does nothing when dates are missing.
- `--js-runtimes` — triggers challenge solving that fails on this host machine.

**Do NOT use `subagent dispatch` for channel discovery on ≤10 channels.** The sequential loop is faster and avoids orphaned-channel bugs.

**Verify channel coverage.** After scanning all channels × 2 tabs, count the results against the config file. Orphaned channels are easy to miss when running many sequential commands. Compare your output section count to the number of handles in the JSON config.

### 3. De-duplicate
   - Read the daily digest file and collect all `Link:` lines.
   - Build a set of already-processed URLs.
   - Skip any URL that exactly matches.
   
   **Republish detection (beyond exact URL matching):** The Economist and similar news channels regularly republish the same content under new video IDs. A video whose URL is new but whose title matches an existing digest entry from the same channel (within 24h) is likely a republish, not new content. Detection heuristics:
   - Compare the discovered video's title against all existing entries for the same channel, using substring similarity (the first 20-40 characters of the title should be enough — e.g. "Can Europe stand up to China on trade?" appears under two different IDs).
   - If a title match is found, check the old URL with `yt-dlp` to confirm it's dead (empty output, exit code 1).
   - If confirmed republish: update the existing entry's `Link:` field to the new URL. Do NOT create a new entry — the summaries are identical.
   - If the old URL is still alive (yt-dlp returns content): both URLs point to real videos — treat as genuinely different content and add the new entry.

### 4. Fetch transcript
   - Use the `youtube-content` workflow for transcript extraction.
   - Run the fetch_transcript.py helper script with `--text-only --timestamps`.
   - If the script succeeds (returns transcript text with timestamps), **also fetch the video description** for enrichment — see "Hybrid: transcript + description enrichment" below. Proceed to summarise.
   - If it returns an empty result, retry without `--language` to get any available transcript.
   - If it returns an IP-block error, pivot immediately to description-based synthesis. Do not retry.
   - If it returns "Transcripts are disabled" (common for FT, Economist, WSJ), pivot to description-based synthesis — do not treat as an API error.

### 4a. Hybrid: transcript + description enrichment (applies when both are available)
   Some publisher videos (Economist, FT) return a usable transcript but also have a rich editorial description. When both sources are available:
   - **Fetch both**: transcript via `fetch_transcript.py`, description via `yt-dlp --print "title" --print "description" --print "uploader" --print "upload_date" "URL"`
   - **Concise Summary**: use the description's editorial hook as the framing thesis. Descriptions often have a cleaner argument hook than raw dialogue.
   - **Detailed Summary**: use the transcript's dialogue flow and timestamp structure for the step-by-step argument reconstruction. The description's chapter markers or editorial framing can structure the narrative arc.
   - This produces consistently richer summaries than either source alone.

   **Practical pattern:** pass both sources into a single subagent dispatch context parameter. The task receives the transcript (for the raw argument flow with timestamps) AND the description (for editorial framing, thesis statement, and chapter markers). The task model then composes summaries that combine both signals cleanly — no post-hoc merging needed.

   **Surprising edge case:** FT shorts sometimes return usable transcripts even though their long-form videos don't. The reason is that Shorts use YouTube's auto-generated captions differently. Do not pre-judge which videos will/won't have transcripts — always try `fetch_transcript.py` first, regardless of channel reputation. The transcript API is intermittently available from this host machine's IP, not predictably blocked.

### 5. Fallback when transcript is blocked (cron / no-browser context)
   - If the transcript API returns an IP-block error (most common in cron/cloud environments), **do not skip the video** — synthesise from description + metadata.
   - Extract description and metadata using:
     ```bash
     yt-dlp --print "title" --print "description" --print "uploader" --print "upload_date" "URL"
     ```
   - The description often contains the creator's own framing, chapter markers, and argument outline — use this to infer the structure.
   - For Shorts, check if the creator pasted the spoken monologue into the description (common pattern).
   - Generate both summaries from the available description text: the Concise Summary should distil the creator's central claim from their description, and the Detailed Summary should reconstruct the argument flow using any chapter markers or structured text in the description.
   - **Do not mark the entry as a fallback** — the delivered format is identical to a transcript-based entry. The source is different but the output quality should be comparable for well-described videos.

### 6. Fallback when transcript is genuinely unavailable
   - If the video has no description beyond auto-generated boilerplate ("Thanks for watching!") and no transcript is retrievable, *then* skip it to avoid hallucinating content.

### 6a. Empty-description enrichment (no transcript AND no description)
   When both the transcript API and the video description return empty:
   - **Do not skip immediately.** The video title itself may contain enough signal for targeted web search.
   - Search for the exact title phrase + creator name.
   - For creator channels (Kyla Scanlon, Nate Herk, etc.), Shorts are often repackaged excerpts from longer-form content (Substack articles, newsletters, podcast clips). The title's thesis statement + named entities can locate the source material.
   - Try multiple platforms: Substack, LinkedIn, Instagram, TikTok, X/Twitter. The same content is often cross-posted.
   - If a linked article or post is found, use it as the source for both summaries. The output quality can match a transcript-based entry — these are the creator's own words, just in a different medium.
   - Only skip when web searches across 2+ queries fail to find anything specific to the video's topic.

   See the companion `youtube-digest-multi-source-enrichment` skill for a complete enrichment pipeline with real-world worked examples from May 2026 (FT shorts on Milei, Trump-Xi summit, Yap stone money). That skill covers the multi-stage search strategy, which sources to try in priority order, and concrete examples of turning 20-40 word descriptions into full-quality summaries via web search.

### 7. Summarise
   - Generate a **Concise Summary** of 3–5 sentences.
   - Generate a **Detailed Summary** of 2–3 short paragraphs that follows the argument step by step.
   - Keep the prose factual and fluffless.

### 8. Write the digest entry

**Best practice: compose the entire updated digest in memory and write it once with `write_file`.**

Patch-based prepending introduces two recurring failures:
- **Double-pipe bug:** pipe-prefixed lines get doubled when the surrounding match context also contains pipes.
- **Ordering fragility:** prepending (newest-first) requires restructuring existing content, which patch handles poorly.

One-shot `write_file` avoids both problems. Compose all new and existing entries as a single markdown string, write it, then verify with a single read.

   - Prepend each entry using this exact shape:
     ```
     ---
     Creator: @[Handle]
     Format: [Short/Long-form]
     Title: [Title]
     Link: [URL]
     References: [Refs]
     Concise Summary: [Summary]
     Detailed Summary: [Summary]
     ---
     ```

### 8a. Description-based summary quality when transcript is blocked

When summarising from descriptions (transcript IP-blocked or disabled), the quality of the output depends on the description type. Treat each case differently:

- **Rich descriptions (FT, Economist, news channels):** typically 50+ words with structured prose and clear argument framing. These can support full-quality summaries indistinguishable from transcript-based ones. Long-form news videos often include chapter markers with timestamps — use these to reconstruct the argument flow.

- **Minimal descriptions (Nicholas Crown, solo creators):** often just a one-line CTA. Use channel-context injection — read the creator's prior digest entries to understand their format and cross-reference the video title with the channel's recent coverage themes.

- **Enrich thin descriptions via web search:** When the description is too thin for a substantive summary (single paragraph + tags, or just a CTA), search the web for parallel coverage. For news/publisher videos, the same interview or topic is often syndicated across multiple outlets.

- **External reference links:** If the description links to a Substack, FT article, academic paper, or other source, fetch it. The linked material often provides the full argument framework that the video only summarises. Extract key thesis statements and weave them into the Detailed Summary.

- **Auto-generated boilerplate:** skip — hallucination risk is too high.

Do not add disclaimers like "transcript unavailable" or "fallback used" — the delivered format is identical to a transcript-based entry. When using subagents for summary generation, inspect their output for auto-generated footnotes and strip them before writing to the digest file.

## Summary generation via subagent

After transcripts are fetched, generate summaries using a subagent — one subtask per video. Feed the full transcript text into the context parameter:

```python
subagent dispatch(
    context="The video discusses [brief characterisation]...\n\nFull transcript:\n[transcript text]",
    goal="Write a Concise Summary (3-5 sentences) and a Detailed Summary (2-3 paragraphs, fluffless step-by-step flow) for this video. Return ONLY the two summaries in the format: Concise Summary: [text]\nDetailed Summary: [text]",
    toolsets=[]  # no tools needed — pure reasoning
)
```

This is highly efficient because each subtask runs in parallel, pure-reasoning subtasks complete in 10–60s each, and the transcript text acts as grounding.

Batch in groups of 3–4 videos per call. Write each digest entry to disk immediately after the summary is received.

## Handling unavailable/deleted videos

When a video is no longer accessible on YouTube:
1. First attempt: `fetch_transcript.py` — returns "Could not retrieve a transcript"
2. Fallback: `yt-dlp --print "title" --print "description" "URL"` — exit code 1 with empty output
3. If both fail: the video may be **deleted** or **republished under a new URL**. Distinguish:
   - **Deleted**: no trace anywhere — skip the video entirely. Note the skipped URL in a section at the bottom of the digest file so the user knows what was lost.
   - **Republished**: a new video from the same channel appears in the same scan with an identical title and content but a different URL. This happens frequently with The Economist (see `references/channel-coverage-patterns.md`). In this case: **do not create a duplicate entry**. Instead, update the existing digest entry's `Link:` field to point to the new URL, since the old one is now dead. This avoids both data loss (preserving the summary) and duplication (not adding a second entry for identical content).
4. **Detection heuristic for republishes**: after fetching the "new" video's title, check the existing digest for entries from the same channel with the same or very similar title. If one exists and the URL differs, cross-reference the content (fetch transcript if available, or compare yt-dlp description output) to determine if it's a republish or genuinely new content.
5. Do not retry, do not attempt browser navigation for dead URLs — the old video is permanently gone.

### yt-dlp silent failure mode
The `yt-dlp --print` command exits with code 1 and returns **empty output** when a video URL is no longer valid. There is no error message to parse. This is distinct from a network failure or missing metadata (which produce stderr output). Mitigation: always check both exit code AND output emptiness. Empty output + exit code 1 = video unavailable. If you don't check both, you may mistake a dead URL for "no results" and proceed with a hallucinated summary.

## Multiple digest updates per day (Evening Update pattern)

The same daily digest file may be updated multiple times in a day. When appending new entries after the initial batch:

1. **Add a subsection header** to distinguish new entries.
2. Place the new section **after** the last existing entry but **before** any "Channels with no content" footer section.
3. If a prior run already noted a channel as "no new content" but that channel now has uploads, remove the channel from the footer no-content list (update the footer in-place rather than duplicating).

## Practical pitfalls

### Patch tool double-pipe issue
When using patch to prepend digest entries, pay close attention to pipe-prefixed metadata lines. The patch tool can double them when the surrounding context contains the same prefix. **Mitigation:** after writing, check for `^||` patterns and collapse to single.

**One-shot write_file requires full file content, not partial read**
The `write_file` tool warns against overwriting a file that was only partially read. Always read the full file (no offset/limit) before composing the replacement.

### Prepend discipline — only today's genuine new entries
When prepending to an existing digest, compose only the genuinely new entries (upload_date in the rolling 24h window, not already present). Do not re-inject old entries or placeholder rows for non-today uploads.

### youtube-transcript-api is intermittently available from this host machine — do not assume permanent block
The API has been blocked in prior runs but **can succeed** on some videos. Do not hard-code the assumption that it will fail. Always try `fetch_transcript.py` first. If it succeeds, you get a much richer summary. If it fails with an IP-block or transcript-disabled error, fall back to description-based synthesis. Do not waste retries — one attempt per video, then pivot.

**Rate-limit pattern (observed May 2026):** The API typically succeeds for the first 5-8 videos across all channels in a single cron run, then starts returning IP-block errors for subsequent calls. The block is session-scoped, not permanent. If a video returns an IP-block error, pivot to description-based synthesis for that video only — do not skip all remaining videos.

**Immediate block variant:** In some sessions the API returns IP-block errors from the very first video, with no successful transcript fetches at all. This is still a session-scoped rate limit, not a permanent ban. When the first video fails with an IP-block error, assume the API is blocked for the remainder of the session and pivot all subsequent videos directly to description-based synthesis without further transcript attempts.

### Double-separator when appending to existing file
When appending entries to an existing digest file, check for consecutive `---\n---` and collapse to single.

### Long discovery scan pitfalls
- Do not rely on flat-playlist timestamps alone for recency.
- Some channel tabs are slow enough to time out; keep discovery bounded and move on if a channel is unavailable.
- Do not pipe `yt-dlp` output directly into an interpreter; write to a temp file first if needed.
- **Transcript API rate-limits mid-session.** In a single cron run, the API may work for the first 8 videos and then start returning IP-block errors for the next 6. This is a rate-limit, not a permanent block. Do NOT treat it as a global error and skip all remaining videos — pivot to description-based synthesis per-video. The API can succeed again in the next session.
- **Channel expanding its content formats.** Nicholas Crown (previously only trading-day market updates) has started posting educational shorts alongside market updates. Scan `--playlist-items 3` on his shorts tab even on non-trading days.
- If a video is clearly in scope but the transcript is unavailable, skip it rather than blocking the digest run.
- Shorts sometimes have usable description text when transcript retrieval fails; treat that as a companion fallback, not the primary path.
- When a video is deleted/unavailable, both the transcript script and yt-dlp will fail. Do one attempt each, then skip.
- **Nicholas Crown posts on non-trading days.** On May 18, 2026 (a Monday), he posted "Worst Investment Mistakes in 2025" — a long-form reflection video from the videos tab, not a shorts market update. Do not assume his schedule is only trading days or only shorts. Check both tabs every day, including the `/videos` tab.
- **Channel republishes content under new URLs.** The Economist regularly republishes the same interview under a different video ID — the old URL goes dead (yt-dlp returns empty output, exit code 1) while the new one appears in the same day's scan with an identical title and content. This is not new content; it's the same video re-uploaded. Check for title similarity against existing digest entries for the same channel before adding a duplicate. Update the old entry's `Link:` field instead.
- **yt-dlp silent unavailability.** When a video URL is dead, `yt-dlp --print` exits code 1 with empty stdout AND empty stderr. There is no error message. You must check exit code (non-zero) AND output emptiness (zero-length) to detect this. An empty result from a non-zero exit is NOT "no transcript available" — it means the video doesn't exist at that URL anymore.

## Accessing companion reference files
This skill carries linked files under `references/`. Access them with the exact tool call syntax:

```python
skill_view(name="youtube-social-media-tracking-digest-workflow", file_path="references/channel-context-injection.md")
```

This is the canonical pattern for reading any linked file in any skill — do not attempt `read_file` on the skill directory, as the `skill_view` tool resolves the correct path and returns the content directly.

## Companion skills
- `youtube-content` for transcript fetching and content transformation.
- `youtube-content-ytdlp-browser-fallbacks` for blocked transcripts or subtitle rate limits.
- `youtube-shorts-description-as-transcript` for Shorts-specific description fallback.
- `youtube-digest-multi-source-enrichment` for web-search enrichment when description is thin and creator is unfamiliar.
- `references/channel-context-injection.md` for reconstructing summaries from minimal descriptions when the creator has a known format.
- `references/nicholas-crown-patterns.md` — format reference for @NicholasCrownYouTube market-update Summaries when transcript is blocked.
