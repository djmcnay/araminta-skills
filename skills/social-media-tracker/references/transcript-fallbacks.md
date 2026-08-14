---
name: youtube-content-ytdlp-browser-fallbacks
description: Fallback workflow for YouTube tracking when transcripts are blocked or subtitles hit rate limits.
ownership: collab
---

# YouTube Content Fallbacks

Use this alongside `youtube-content` / social-media tracking when transcript retrieval is unreliable.

## When to use
- `youtube-transcript-api` is blocked from the current IP
- `yt-dlp` subtitle downloads return HTTP 429
- Shorts/videos have metadata but no accessible transcript

## Reliable metadata path

### Preferred approach (small channel sets, ≤10 channels)
Use `yt-dlp --playlist-items 1` on each tab (both `/videos` and `/shorts`). This returns real upload dates without RSS or JSON parsing:

```bash
yt-dlp --playlist-items 1 --print '%(webpage_url)s' --print '%(title)s' --print '%(upload_date)s' --print '%(uploader)s' 'https://www.youtube.com/@Handle/shorts'
yt-dlp --playlist-items 1 --print '%(webpage_url)s' --print '%(title)s' --print '%(upload_date)s' --print '%(uploader)s' 'https://www.youtube.com/@Handle/videos'
```

High-volume channels (FT, Economist, Crown on active days) need `--playlist-items 3` to catch all uploads within a 24h window.

### Template strings are unreliable on some yt-dlp versions
Do NOT use the `--print "PREFIX:%(field)s||DELIM:%(other)s"` pattern — it prints the literal template text (with unresolved `%(field)s` placeholders) on some builds. Use separate `--print '%(field)s'` calls instead, one per field.

### What NOT to use
- **`--flat-playlist --dump-single-json`** — triggers JS challenge errors on some systems; too slow and unreliable.
- **RSS feeds** (`feeds/videos.xml`) — return 404 for most channels in 2026.
- **`--flat-playlist` for dates** — returns `DATE:NA` for upload dates in the flat listing.
- **`--date`** — silently does nothing when dates are missing from flat-playlist output.
- **`--js-runtimes`** — triggers challenge solving that often fails in headless environments.

## Transcript fallback path

### With browser available (interactive CLI, dashboard)
1. Open the video page in the browser.
2. Read `window.ytInitialPlayerResponse.microformat.playerMicroformatRenderer` for publish date and other metadata.
3. Read the page body or description text for the creator's own framing.
4. If captions are exposed in the player response but direct fetches are blocked, treat the transcript as unavailable and summarise from title + description + page context.

### Without browser (cron / headless / scheduled jobs)
No browser path is available. Use `yt-dlp` description extraction instead:
```bash
yt-dlp --print "title" --print "description" --print "uploader" --print "upload_date" "URL"
```
The description field is your primary signal:
- Long-form videos often include structured chapter markers with timestamps — use these to reconstruct the argument flow and derive a Detailed Summary.
- Short creators frequently paste the full spoken script into the description.
- If the description is rich enough, synthesise both Concise and Detailed summaries from it at the same quality standard as a transcript-based entry. Do not mark the entry as a degraded fallback.
- If the description is empty or auto-generated boilerplate, skip the video — do not hallucinate content.

## Audio/Video Extraction (host-machine-specific)

When downloading YouTube content (audio or video) on this host machine, the standard web client triggers JS challenge errors because no EJS runtime is configured. Use the **Android client API** instead:

```bash
# Audio-only extraction — reliable on this host machine
yt-dlp --extractor-args "youtube:player_client=android" \
       --extract-audio --audio-format m4a --audio-quality 0 \
       --embed-metadata \
       --output "%(title)s [%(channel)s].%(ext)s" \
       "URL"
```

**Why this works:** YouTube's web player now uses n-parameter JS challenges. The Android client API bypasses them entirely. Format 18 (360p MP4 with audio) is the reliable fallback when higher formats fail.

**Note:** The Android client may warn about missing GVS PO Tokens. This warning is cosmetic — format 18 downloads proceed normally.

**Do NOT use:** `--js-runtimes node` or `--remote-components` — these trigger challenge solving that fails on this host machine. Stick to `--extractor-args "youtube:player_client=android"`.

## Practical rule
Do not stall on transcript failures. If the video is clearly in scope and the description provides usable content, write a full-quality digest entry. Only skip when both transcript AND usable description are absent.

- **Cron jobs / headless**: always extract the video description via separate `--print '%(description)s'` calls (not template strings). For Long-form videos with chapter markers, use the timestamped structure to reconstruct the argument flow. For news channels (FT, Economist), descriptions are typically rich enough to support full-quality summaries. For creator channels with thin descriptions, use channel-context injection — read prior digest entries to understand the creator's format and cross-reference with the video title.
- **Writing the digest**: compose the complete updated digest in memory and write it once with `write_file` — do NOT use `patch` to append entries. Patch-based prepending introduces the double-pipe bug (`|` prefixed lines get doubled to `||`) and makes ordering fragile. One-shot write avoids both problems and allows a single verification read afterwards.
- **External references in descriptions**: when the description links to an external source (Substack, FT article, academic paper), fetch it — the linked material often provides the full argument framework that the video summarises.
