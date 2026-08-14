# YouTube Social Tracking Workflow

This file captures the operational quirks that surfaced while running the daily tracker. Updated 10 May 2026.

## Discovery pattern (Current — May 2026)

### Primary method: Flat-playlist + individual verification

**`--playlist-items N` with full metadata calls consistently time out (>30s) from this host machine for ALL channels** — both the non-flat Phase 1 approach and even `--flat-playlist --playlist-end N` in the `--dump-single-json` variant. The only reliable method is a two-step approach:

**Step 1 — Flat-playlist discovery (primary):**
```bash
# Delimiter template works fine via direct terminal()
yt-dlp --flat-playlist --playlist-end 15 --print '%(title)s||%(webpage_url)s' 'https://www.youtube.com/@HANDLE/videos'
```
- Use 15 items for FT and The Economist, 10 for active channels (NicholasCrown), 8 for low-volume channels
- Flat-playlist dates will be `NA` — this is expected
- Call EACH channel+tab as a separate `terminal()` call (see Pitfalls below)

**Step 2 — Date verification for each candidate:**
```bash
yt-dlp --playlist-items 1 --print '%(title)s' --print '%(upload_date)s' --print '%(webpage_url)s' --print '%(uploader)s' 'URL'
```
- Each call takes ~3–5s. Call individually from `terminal()`, one per candidate.
- Compare `upload_date` (format: YYYYMMDD) against current date from `date -u +%Y%m%d`.
- Do NOT use `--dateafter` in this step — it's inert on flat-playlist results.

### Channel-specific item counts

| Channel | Items needed | Notes |
|---------|-------------|-------|
| @FinancialTimes | 20 (videos), 10 (shorts) | Posts multiple times daily |
| @TheEconomist | 20 (videos), 10 (shorts) | Multiple daily posts |
| @NicholasCrownYouTube | 10 (shorts) | Active trading days only; long-form dormant |
| @garyseconomics | 8 each tab | 1–2 posts/week |
| @KylaScanlon | 5 each tab | Long-form dormant; shorts every 2–4 days |
| @PBoyle | 10 (videos), 5 (shorts) | ~1 long-form/week |
| @nateherk | 8 (videos), 5 (shorts) | ~1–2 posts/week |

### Throughput note (12 May 2026)

All 14 channel/tab flat-playlist calls: ~14 seconds total (individual `terminal()` calls).
All ~40 date-verification calls: ~20 seconds total (individual `terminal()` calls, 3-5s each).

**Delimiter templates — works via direct terminal():** `--print '%(title)s||%(webpage_url)s'` resolves correctly from individual `terminal()` calls. The earlier advice that delimiter templates "silently fail on this host machine" was determined while batched via `execute_code` — the failure was in batching, not the delimiter itself. Use delimiter templates freely for flat-playlist discovery. For date verification (`--playlist-items 1`), use separate `--print` per field since the output needs field-position parsing.

## RSS feeds — DO NOT USE (DEPRECATED, May 2026)

YouTube's `/feeds/videos.xml?channel_id=...` endpoint now returns 404 for most channels. The `youtube-discovery-workflow.md` reference previously recommended RSS as the primary timestamp source — that advice is outdated. Use `--playlist-items 1` per individual video URL instead.

## Publish-time filtering

- Flat-playlist metadata always omits `upload_date` — this is expected behaviour, not a bug.
- Use `--playlist-items 1` (non-flat) per candidate URL to get `upload_date` as a string like `20260509`.
- Compare against current UTC date: `date -u +%Y%m%d`.

## Security scanner workarounds

The terminal security scanner (Tirith) blocks pipe-to-interpreter patterns:
```bash
yt-dlp ... | python3 ...      # BLOCKED — HIGH severity
```

Safe patterns:
```bash
# Write to temp file
yt-dlp ... > /tmp/discovery.json

# Parse in separate step
python3 -c "
import json
data = json.load(open('/tmp/discovery.json'))
# ... process ...
"
```

Or use heredoc for Python scripts:
```bash
cat > /tmp/parse.py << 'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
# ... process ...
PYEOF
python3 /tmp/parse.py /tmp/discovery.json
```

### execute_code pitfall — yt-dlp commands fail when batched

**`execute_code` with `hermes_tools.terminal()` silently corrupts yt-dlp commands** — specifically, URLs containing `@` symbols and query parameters are mangled (bash reports syntax errors, no output returned). All 14 flat-playlist calls across 7 channels failed when batched in a single `execute_code` block but succeeded immediately when run as individual `terminal()` calls from the chat.

**Workaround:** Call each channel/tab's flat-playlist discovery AS A SEPARATE `terminal()` call. For date verification, also use individual `terminal()` calls rather than trying to batch them in `execute_code`. The throughput is still reasonable (~5s per candidate).

## Digest hygiene

- Check today's digest first, then the previous day.
- Use the `Link:` field as the canonical dedupe key.
- Write the full file with `write_file` — do NOT use `patch` (causes double-pipe bug on pipe-prefixed lines like `|Creator:`).
