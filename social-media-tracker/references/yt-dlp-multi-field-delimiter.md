# Multi-Field yt-dlp Delimiter Pattern

## Problem
When verifying individual YouTube video metadata (title, upload_date, webpage_url, uploader), calling `--print '%(title)s' --print '%(upload_date)s' ...` separately produces readable output but is fragile to parse programmatically — the four lines can be misaligned across multiple parallel calls. Using `execute_code` to batch-verify URLs also risks silently corrupting `@`-containing URLs from `terminal()` output.

## Solution
Use a single `--print` with pipe-delimiters and direct `terminal()` calls, then parse the one-line output in `execute_code`:

```bash
yt-dlp --playlist-items 1 --print '%(title)s||%(upload_date)s||%(webpage_url)s||%(uploader)s' 'URL'
```

Output format:
```
Title||20260519||https://www.youtube.com/watch?v=XXXX||Uploader Name
```

Parsing in execute_code:
```python
for line in yt_dlp_output.strip().splitlines():
    title, date_str, url, uploader = line.split('||', 3)
    # date_str is YYYYMMDD
    if date_str in ('20260519', '20260518'):
        new_videos.append((title, url, uploader, date_str))
```

## Why This Works
- Direct `terminal()` calls do not corrupt `@` symbols (unlike `execute_code` batching).
- A single `--print` avoids the risk of multi-field drift when yt-dlp interleaves warnings or JS runtime messages between separately-ordered print lines.
- The `||` delimiter is safe because `|` never appears in standard YouTube titles or uploader names.

## When to Use
- Date verification for each candidate URL during social media tracking discovery.
- Any situation where you need to fetch 3+ metadata fields per YouTube video in a cron or batch pipeline.

## When NOT to Use
- When you only need one field — use a bare `--print` or `--flat-playlist` discovery instead.
- When an interactive session makes multi-line debugging output preferable.
