# yt-dlp Scan Command Patterns

Proven command patterns for the social-media tracking workflow. These account for the fact that `--flat-playlist` consistently returns `NA` for `upload_date` in this environment.

## Android client workaround (audio/video downloads, JS challenge bypass)

When downloading videos or audio (not just metadata scanning), YouTube's web client triggers n-parameter JS challenges that fail on this host machine (no proper EJS runtime). The Android client API bypasses this entirely:

```bash
yt-dlp --extractor-args "youtube:player_client=android" \
       --extract-audio --audio-format m4a --audio-quality 0 \
       --embed-metadata \
       --output "%(title)s [%(channel)s].%(ext)s" \
       "URL"
```

**When to use:** Any `yt-dlp` invocation that actually downloads media (audio extraction, video download) rather than just printing metadata.

**What happens without it:**
- `yt-dlp` tries web client → encounters JS challenge → attempts to solve with node → fails → "This video is not available"
- Even with `--js-runtimes node --remote-components ejs:github`, the challenge solver is not properly set up on this host machine

**Warning:** Some Android formats may be SABR-only (no direct URL). Format 18 (360p MP4 with audio) is the reliable fallback — yt-dlp auto-selects it when higher formats fail. For audio-only extraction this is fine; the audio stream is clean.

**Do NOT use for metadata scanning** — the `--playlist-items --print` pattern in the sections below works without the Android client flag because it uses a different API path. Only use `--extractor-args youtube:player_client=android` when actually downloading media.

## Channel tab discovery (bounded) — sequential shell loop

**This is the primary method for ≤10 channels.** A single loop completes all scans in ~2 minutes without subagent dispatch overhead:

```bash
for handle in "KylaScanlon" "NicholasCrownYouTube" "PBoyle" \
              "garyseconomics" "TheEconomist" "FinancialTimes" "nateherk"; do
  echo "=== @$handle videos ==="
  yt-dlp --playlist-items 1-5 \
    --print '%(webpage_url)s' --print '%(title)s' --print '%(upload_date)s' --print '%(duration)s' \
    "https://www.youtube.com/@${handle}/videos" 2>/dev/null
  echo "=== @$handle shorts ==="
  yt-dlp --playlist-items 1-5 \
    --print '%(webpage_url)s' --print '%(title)s' --print '%(upload_date)s' --print '%(duration)s' \
    "https://www.youtube.com/@${handle}/shorts" 2>/dev/null
  echo ""
done
```

Each channel requires 2 calls — one for `/videos`, one for `/shorts`. The `2>/dev/null` at the end of each yt-dlp call suppresses warnings about missing JS runtimes (cosmetic — doesn't affect metadata output).

Use separate `--print '%(field)s'` calls per field. Pipe-delimiter templates (`--print "URL:%(field)s||TITLE:%(title)s"`) silently print literal template text including unresolved placeholders on this host machine — never use them.

## Full-metadata resolution (per-video)

After the discovery pass identifies candidates from the last 24h, resolve additional metadata:

```bash
yt-dlp --playlist-items 1 --skip-download \
  --print '%(webpage_url)s' --print '%(title)s' --print '%(upload_date)s' --print '%(duration)s' \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

This works with either `youtube.com/watch?v=ID` or `youtube.com/shorts/ID` URLs. Do NOT pass `--flat-playlist` — this forces full metadata extraction with real dates. Use separate `--print '%(field)s'` calls per field — pipe-delimiter templates fail silently on this host machine.

## Duration-based Short detection (authoritative)

**Tab origin is NOT reliable for format classification.** Some channels post long-form content under `/shorts`. Cross-check every candidate with duration:

```bash
yt-dlp --print "%(duration)s" "https://www.youtube.com/watch?v=VIDEO_ID"
```

Rules:
- Duration < 60 seconds → `Short`
- Duration ≥ 60 seconds → `Long-form`

Proven with real data: The Economist short at 127s appears under `/shorts` but is classified as Long-form by duration (the video is a ~2-minute opinion segment, not a <60s Short).

## Batch discovery via subagent dispatch (only for 15+ channels)

Reserve `subagent dispatch` for when the sequential loop would take more than ~5 minutes (roughly 15+ channels):

```python
# Pattern: 3 parallel tasks per batch, each handles one channel
# First batch: channels 0-2
# Second batch: channels 3-5
# Third batch: remaining channels
```

**CRITICAL: After batching, verify every handle from the config has been scanned.** The most common failure mode is an orphaned channel — especially the last channel in an uneven batch — that gets missed because neither batch handler picked it up.

## Date filter logic

```python
from datetime import date, timedelta

today = date.today().strftime("%Y%m%d")  # e.g. "20260511"
yesterday = (date.today() - timedelta(1)).strftime("%Y%m%d")  # "20260510"

# Uploads from yesterday are within "last 24 hours" for a morning cron
is_recent = upload_date in (today, yesterday)
```

Note: yt-dlp's `upload_date` is YYYYMMDD with day granularity. A video uploaded at 23:00 UTC on yesterday will still qualify at 06:00 today.

## Publisher channels (Economist, FT, Bloomberg, WSJ)

These channels frequently **disable transcripts** deliberately — the `youtube-transcript-api` returns `{"error": "Transcripts are disabled for this video."}`. This is NOT an IP block or API failure. Handle as:
1. Fetch description via `yt-dlp --print "title" --print "description" --print "uploader" --print "upload_date" "URL"`
2. Publisher descriptions are usually substantive (50+ words) and include the video's argument structure.
3. Synthesise summaries from the description text.
4. Do NOT note "fallback" in the output — the delivered format is identical.

## Hybrid: transcript + description enrichment

Some publisher videos (Economist, FT) *do* return a transcript. When available, use both:
1. Fetch transcript via `fetch_transcript.py` — yields the panelist dialogue and timestamp structure
2. Also fetch the description — often contains the editorial framing that the transcript lacks

Combine them: use the description's editorial hook as the Concise Summary's framing, and the transcript's dialogue flow for the Detailed Summary's step-by-step structure. The description often has a cleaner argument thesis than the raw dialogue.

Check: always try the transcript API first. If it succeeds (non-empty output), also grab the description for enrichment. Only fall to description-only if the transcript fails.
