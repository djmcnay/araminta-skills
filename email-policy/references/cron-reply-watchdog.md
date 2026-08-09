# Cron Reply Watchdog Pattern

## When to use

the user has sent an outbound email (or draft was approved) and is waiting for a **vendor/human reply**. Instead of asking him to check manually, set up a recurring cron job that polls the appropriate inbox and surfaces the reply on WhatsApp the moment it arrives.

## Recipe

```
hermes cron create \
  --name "descriptive-name-reply-watch" \
  --prompt "<see below>" \
  --schedule "every 30m" \
  --repeat 30 \
  --skill email-policy \
  --deliver origin
```

Parameters:
- `--repeat 30`: ~15 hours of coverage (30 × 30min). Enough for a business day + next morning.
- `--skill email-policy`: ensures triage rules are loaded.
- `--deliver origin`: delivers to whatever surface you're currently on (usually Discord/CLI). The cron prompt then decides whether to forward to WhatsApp.

## Prompt template

```
Check the [assistant-email] inbox for new replies from {sender-domain} on the {topic} threads (thread IDs: {thread-id-1}, {thread-id-2}). Use mcp_agentmail_list_threads with inboxId='[assistant-email]' and check if there are new messages from {sender}.

If there's a new message from either thread that you haven't reported before, extract the key content and deliver it to the user on WhatsApp (target: 'whatsapp').

The message should be brief and actionable — just what they said and whether they're offering a replacement, repair path, or asking for more info. Don't add editorialising. Prefix with "{vendor-flag-icon}" and include their name. If the message has no new substantive content, stay silent — don't ping for "no new messages".
```

## Key rules

1. **Silent on no-news**: the prompt must explicitly say "stay silent if nothing new" — otherwise the cron job pings with "nothing new" every cycle.
2. **Thread-specific, not inbox-wide**: target specific thread IDs so the watch doesn't surface unrelated mail.
3. **WhatsApp delivery from cron**: the cron job itself delivers to `origin` (the user's current surface), but the prompt instructs it to forward to WhatsApp. This works because the cron job's agent can use the WhatsApp send tool.
4. **Duration bounds**: 30 repeats × 30min = 15h. If the user still needs it after that, extend or re-create with more repeats.

## Past examples

| Topic | Sender | Cron created | Result |
|---|---|---|---|
| Timemore scale RMA | hello@timemore.com (Sandy/Chloe) | 2026-05-18 | Watching two threads, delivers to WhatsApp on reply |
