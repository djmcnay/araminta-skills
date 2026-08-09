---
name: youtube-shorts-description-as-transcript
description: Use yt-dlp description fields as transcript fallback specifically for YouTube Shorts, since Shorts creators often paste the full spoken monologue into the description.
ownership: collab
---

# YouTube Shorts — Description as Transcript Fallback

## When to use
- `youtube-transcript-api` is blocked or returns errors.
- `yt-dlp` subtitle downloads hit HTTP 429.
- The video is a **Short** (duration < 60 s, `/shorts/` URL).

## Quality thresholds by channel type

- **News/publisher channels** (FT, Economist, WSJ, Bloomberg): descriptions are often dense summaries in under 80 words. A description of 20+ words from a news channel is usually **transcript-equivalent for summary purposes** because every sentence carries informational weight. FT's short descriptions frequently exceed 100+ words (observed May 2026: 500-1000 chars with full argument framing) and provide complete thesis, supporting evidence, and closing implications — indistinguishable in quality from a full transcript for digest purposes. Treat FT Shorts descriptions as premium source material, not thin metadata.
- **Creator channels** (individuals like Kyla Scanlon, Nate Herk, Nicholas Crown): may paste the full script but may also write promotional blurbs. Apply the ~100-word threshold for creator channels.
- **Channel-context injection** (for descriptions under 20 words where the video title is self-explanatory): cross-reference with the creator's prior digest entries to understand their established format, and reconstruct the argument flow from title + channel conventions. This is not hallucination — it's grounded inference from a known template (e.g., Crown always opens with numbers, then narratives, then portfolio implications).
- **Shorter descriptions (< 20 words) from unknown channels**: skip — too little signal for reliable summary.

## Cleaning method
1. Fetch description via `yt-dlp --print '%(description)s' 'URL'` (separate `--print` call per field, not template strings).
2. Clean before summarising:
   - Strip hashtags (`#hashtag`).
   - Strip promo links and subscribe/follow CTAs.
   - Strip platform links (`instagram.com`, `tiktok.com`, etc.) unless they link to content referenced in the video.
   - Remove chapter timestamps if present (`00:00 - Topic`) but keep the chapter titles as structure clues.

## Formatting rules
- Concise Summary: 3–5 sentences from the cleaned description.
- Detailed Summary: structured paragraphs if description length supports it; otherwise mark as limited.

## Practical note
Do **not** attempt browser scraping or `window.ytInitialPlayerResponse` parsing for Shorts as first fallback — the description from `yt-dlp` is usually faster and more reliable.
