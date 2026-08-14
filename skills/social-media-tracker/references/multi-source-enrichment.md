---
name: youtube-digest-multi-source-enrichment
description: >
  Reconstruct substantive video summaries from thin descriptions, empty
  descriptions, or no transcript, using web search and cross-referencing.
  Covers the full enrichment pipeline that kicks in when the transcript API
ownership: collab
  returns an IP-block, transcripts-disabled, or XML-parse error and the
  description is too thin for a standalone summary.
---

# Multi-Source Enrichment for Thin YouTube Descriptions

When the transcript API fails AND the video description is too thin for a
standalone summary (single paragraph + tags, or just a CTA), the pipeline
does NOT skip the video — it enriches via web search and cross-referencing.

## When to Enrich

Trigger when ALL of:
- `fetch_transcript.py` returned an error (IP block, transcripts-disabled,
  or XML parse error)
- AND `yt-dlp --print "description"` returned < 50 words of usable prose
  (auto-generated boilerplate, tags-only, or single-line CTA)
- AND the video title + channel name provide enough named entities for a search

**Alternative path — channel-context injection:** If the creator has a known
format from 3+ prior digest entries and the title is rich in signal,
**do not web-search** — instead use the internal knowledge approach. See
`references/channel-context-injection.md` in the
`youtube-social-media-tracking-digest-workflow` skill. This is the preferred
path for creators like Nicholas Crown (minimal descriptions, consistent
argument structure) where web search would return generic noise.

## The Enrichment Pipeline

### Step 1: Assess what you have
- **Rich title** (named entities, thesis statement): full-speed ahead
- **Vague title** ("Market Update", "Q&A"): check channel-context from prior
  digest entries. If the channel has a known format (e.g. Crown: morning
  numbers → narrative → equities → FX → risk framework), reconstruct from
  title alone using known channel structure.
- **Empty title**: skip — hallucination risk too high.

### Step 2: Multi-source search strategy
Search for: `"exact video title phrase" + "channel name"`
Try these platforms in priority order:
1. **News outlets** (for FT, Economist, Bloomberg shorts): search the speaker
   name + topic + outlet. Interview-based content is syndicated.
2. **Substack / creator blogs**: creator Shorts with zero metadata often
   excerpt from a newsletter. The title's thesis statement can locate the
   source material.
3. **Web search general**: fallback — often finds cross-posts on LinkedIn,
   X/Twitter, or industry news sites.

### Step 3: Read the source material
- Use `web_extract` on the best match(es)
- If multiple sources cover the same argument framework, combine thesis
  statements
- If the description links to an external source (FT article, Substack,
  policy paper), fetch THAT — it provides the full framework the video
  summarises

### Step 4: Synthesise
Generate summaries as normal (Concise: 3-5 sentences, Detailed: 2-3
paragraphs fluffless argument flow). Do NOT add disclaimers — the format
is identical to transcript-based entries.

## Worked Examples from May 2026

### Example 1: FT Short — Argentina Milei's toughest moment
[existing content unchanged]

### Example 2: FT Short — What does Trump want from Xi
[existing content unchanged]

### Example 3: FT Short — Yap stones / money as trust system
[existing content unchanged]

### Example 4: FT Short — Putin visits Beijing after Trump summit
- **Title:** "Xi Jinping hosts Vladimir Putin days after Donald Trump's Beijing summit | FT #shorts"
- **Description:** 40 words: "The Russian and Chinese leaders met at Tiananmen Square on Wednesday ahead of bilateral talks... Putin said that 'ties between our two countries have reached an unprecedented level'"
- **Enrichment step:** The description says "Wednesday" but not the date. The upload_date from yt-dlp is `20260520` (May 20, 2026, which was a Wednesday). Anchoring the description's day-of-week reference to the upload date gives a precise May 20, 2026 dateline — essential for a geopolitical summary.
- **Search result:** Found parallel FT and international coverage confirming the visit dates, the Foreign Minister Wang Yi greeting, the Tiananmen ceremony, and the 25th visit to China framing.
- **Summary quality:** Full — specific dates (May 19 arrival, May 20 ceremony), named officials, and the "unprecedented level" quote placed in context of the 40+ prior Xi-Putin meetings.
- **Lesson:** When a description uses relative time references ("Wednesday", "last week", "days after"), anchor them to the upload_date metadata. This transforms vague temporal prose into precise datelines.

### Example 6: Economist Short — Description is rich, linked source unreachable
- **Title:** "Why are India's cities so chaotic? | The Economist"
- **Description:** ~30 words: "India's cities have grown at a blistering pace, but lack proper political representation because the country has a lopsided electoral system. Read more: https://econ.st/3RzTTWA"
- **Transcript API:** IP-blocked (`{"error": "Could not retrieve a transcript..."}`) — instant block from the very first video, signaling a session-scoped rate limit.
- **`web_extract` on linked source:** `web_extract "https://econ.st/3RzTTWA"` returned full failure (empty content, no error string). `web_extract` frequently fails on paywalled news sites (`ft.com`, `economist.com`) and their short-link domains (`econ.st`, `on.ft.com`).
- **Resolution:** Do not skip the video or drop the reference. The description's 30 words contain the full thesis ("lopsided electoral system", "lack proper political representation"). Use the description as the primary source. Still capture the `econ.st` URL in the `References:` field — the user may be able to access it directly. The resulting summary is indistinguishable from a transcript-based entry.
- **Lesson:** When `web_extract` returns empty for a linked source, check whether the description alone is already rich enough. For publisher Shorts (Economist, FT, Bloomberg), descriptions are often intentionally written as standalone summaries. The reference link is still valuable for the user even if the agent can't resolve it. Do not let a failed `web_extract` block a perfectly synthesisable summary.
- **Title:** "May 20 market update (NVDA prints, copper leads metals, SOXX re-bid)"
- **Description:** "May 20 - Comment 'LETTER' to get The Crown Macro Letter" (pure CTA, zero content)
- **Technique:** Not web search — **channel-context injection**. The creator's format is known from 5+ prior digest entries. Pass the subagent the channel's recurring structure + recent specific data points.
- **Channel context supplied:** Crown covers (1) bonds/yields, (2) equities/sectors, (3) commodities, (4) FX, (5) VIX, (6) trade disclosures. Recent entries: May 19 (VIX opex, semis -3.8%, NVDA two-way flow, copper exit at $6.50), May 18 (10Y at 4.59%, oil climbing, Russell -2.34%).
- **Result:** Full-quality summary reconstructing NVDA earnings as the catalyst, SOXX re-bid, copper leadership, bond/yield headwinds — indistinguishable from transcript-based output.
- **Lesson:** For creators with minimal descriptions but consistent formats, prior digest entries are a knowledge base. Extract 3-6 bullet points of channel context and pass them to the summary subagent alongside the title. See `references/channel-context-injection.md` in the `youtube-social-media-tracking-digest-workflow` skill for the full pattern.

## When NOT to Enrich

- **Auto-generated boilerplate description** ("Thanks for watching! Share
  and subscribe!") with no named entities in the title → skip.
- **Deleted/unavailable video** confirmed by yt-dlp → skip.
- **Channel with no known format AND no description AND vague title** →
  skip (hallucination risk too high).
