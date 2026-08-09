# Cron Job Configuration Patterns for Price-Spy

## Silent Mode Cron (Default)

```yaml
job_id: price-spy-daily
name: "price-spy-daily"
schedule: "50 11 * * *"
deliver: "telegram:<your-chat-id>"  # explicit numeric chat ID
enabled_toolsets: ["send_message", "web", "terminal", "file", "browser"]
prompt: |
  Price-spy run (silent mode).
  
  RUN: Read items.json from the price-spy skill directory. For each active item, 
  check price using the appropriate price_source skill (amazon) or best-efforts 
  anti-detection browser scrape. Update items.json with latest prices and observations. Log to 
  price_history.
  
  If an alert condition is met during the run (price crossed below target, used 
  condition appeared, item disappeared/reappeared), send a Telegram alert 
  immediately to telegram:<your-chat-id> using the send_message tool.
  
  Alert format:
  ```
  🔔 Price Spy alert
  
  [Item name]
  Now: £XX.XX ([condition])
  Target: £XX.XX
  [URL]
  
  Want me to add to basket? (Amazon only)
  ```
  
  If nothing notable: respond with exactly [SILENT] (no other text) to suppress 
  delivery. This is the default behavior for cron runs — only surface exceptions.
  
  Do not produce a summary report unless explicitly asked to "report" or "run 
  and report".
```

## Report Mode Cron (Explicit)

Use `"run and report"` in the prompt when a visible daily summary is wanted:

```yaml
prompt: |
  Price-spy run and report.
  
  ... same run steps ...
  
  Then produce a summary report of notable changes (threshold crossings, 
  availability changes, significant price movements). If nothing notable, 
  output the full watchlist table — the user explicitly asked for a report.
```

## Key Configuration Rules

| Setting | Silent Mode | Report Mode |
|---------|-------------|-------------|
| `deliver` | `telegram:<chat_id>` | `telegram:<chat_id>` |
| Prompt contains | "silent mode" or "run only" | "run and report" |
| Worker emits | `[SILENT]` when nothing notable | Full table when nothing notable |
| Multi-target | NEVER | NEVER |
| `deliver: "origin"` | NEVER | NEVER |

## Why Not `deliver: "telegram,discord"`?

The Hermes scheduler delivers the worker's final response to **ALL targets listed in `deliver`** simultaneously. There is no conditional fallback logic. If the worker emits `[SILENT]`, it goes to both Telegram and Discord. If the worker emits a report, it goes to both. The silent-mode suppression only works when there is exactly ONE delivery target.

## Why Not `deliver: "origin"`?

`origin` resolves to the chat where the cron job was created. If created from Discord, all cron deliveries go to Discord — bypassing the intended Telegram primary channel.

## Telegram Chat ID

Use the **numeric chat ID** (e.g., `<your-chat-id>`), not the display name (`"the user McNay (dm)"`). The delivery layer's `int()` parsing fails on display names. Discover the chat ID via `send_message(action='list')` and use the `chat_id` field from any Telegram target.

## Toolset Requirements

The cron worker needs these toolsets to execute the full run + alert flow:
- `send_message` — for Telegram alert delivery
- `web` — web_search, web_extract for fallback scraping
- `terminal` — for JSON validity checks, other shell commands
- `file` — read_file, write_file, patch for items.json updates
- `browser` — browser_navigate, browser_console for DOM extraction (anti-detection browser)

Missing `send_message` = alerts silently fail to deliver.