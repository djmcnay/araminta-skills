---
title: Confirmed Inbound Scan — Step-by-Step Workflow
updated: 2026-05-20
skill: email-policy
---

# Confirmed Inbound Scan Workflow

This reference is a concrete, copy-pasteable checklist for the **confirmed cross-check** step in `email-policy`. It captures exact commands, fallback patterns, and edge cases that appeared during real case-scan sessions.

## When to run

- Before drafting/sending any outbound email for an open case.
- During every scheduled cron case scan.
- When entering interactive mode after a suspected webhook outage or gateway restart.

## Participants → search mapping

Extract **all** email addresses from the `Participants:` section of each open case card. Group them into two categories:

| Category | Examples | Scans needed |
|----------|----------|--------------|
| Vendor / human | `hello@timemore.com`, `administration@discovery.co.za` | AgentMail + Gmail |
| the user / Minty | `[user-email]`, `[assistant-email]` | AgentMail only (for CC/forward detection) |

If the user has performed an **identity flip** (emailed vendor directly from Gmail because AgentMail is blocked), add the vendor address to the Gmail scan even if it wasn't originally in `Participants:`. Update the case card to include it.

## Exact cross-check commands

### 1. AgentMail — both inboxes

```
mcp_agentmail_list_threads(inboxId="[assistant-email]", after="<YYYY-MM-DD>T00:00:00Z", limit=20)
mcp_agentmail_list_threads(inboxId="[assistant-email-2]", after="<YYYY-MM-DD>T00:00:00Z", limit=20)
```

**Date rule:** Use the case's last known inbound event date, or 7 days ago if none.

**Label inspection:** Read the `labels` array for every thread returned. Key states:
- `["sent"]` only — outbound from Minty; not actionable unless a reply is nested inside.
- `["received", "unread"]` — candidate inbound; fetch with `get_thread`.
- `["received", "unread", "read"]` — often a CC or forward from the user (sender is `[user-email]`). NOT a vendor reply, but may contain new context.
- `["received", "read"]` — already reviewed; skip unless it appeared since last scan time.

**Pitfall:** AgentMail's `unread` label can be stale. Never trust `labels` alone without also checking `timestamp` against the last scan time.

### 2. Gmail — vendor participant search

```bash
PYTHON_BIN="$HOME/.hermes/hermes-agent/.venv/bin/python"
$PYTHON_BIN ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py \
  gmail search "from:(vendor1@domain.com OR vendor2@domain.com) after:YYYY/MM/DD" --max 20
```

**Pitfall — `body_text` truncation:** The search result JSON includes a `body_text` field, but it is frequently truncated to a short preview (often the first paragraph only). If the preview looks promising or ambiguous, **immediately fetch the full message:**

```bash
$PYTHON_BIN ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py \
  gmail get "<message_id>"
```

Use the `body_html` field in the `get` response for the complete content; `body_text` may still be truncated. Strip HTML tags if you need plain text for classification.

### 3. Gmail — "the user-sent" identity-flip check

If the user has emailed a vendor directly from Gmail (identity flip), also run:

```bash
$PYTHON_BIN ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py \
  gmail search "from:[user-email] to:vendor@domain.com after:YYYY/MM/DD" --max 10
```

This confirms the user's outbound was actually sent, and reveals any CC/forward patterns.

## What counts as a missed reply

| Source | Signal | Action |
|--------|--------|--------|
| AgentMail | Thread `timestamp` newer than last scan, sender is vendor, labels include `received` | Fetch full thread, classify, update kanban |
| Gmail | Search result `date` newer than last scan, sender is vendor, message not previously recorded in case History | Fetch with `gmail get`, classify, update kanban |
| Gmail | Bounce / NDR (`mailer-daemon`, `postmaster`) | Record bounce per `references/bounce-recording-procedure.md` |
| AgentMail CC | Thread sender is `[user-email]`, CC'd to `[assistant-email]` | the user forwarded context; update case but do not treat as vendor reply |

## If a missed reply IS found

1. **Stop** — do not proceed with drafting/sending for this case.
2. **Surface to the user immediately** with: who replied, what they said, updated recommended action.
3. **Update kanban card** inline (History, Steps, Latest summary, Chaser due).
4. **Mirror to vault** (`araminta-vault/kanban/cases/open/<slug>.md`).
5. **Post a kanban comment** if the CLI schema is healthy; otherwise the inline body update serves as audit trail.

## Kanban CLI schema-drift fallback

If `hermes kanban list`, `hermes kanban show`, or `hermes kanban comment` fail with `no such column: session_id` (or similar), fall back to direct SQLite immediately:

```python
import sqlite3, os

db = sqlite3.connect(os.path.expanduser('~/.hermes/kanban.db'))
rows = db.execute("SELECT id, title, body FROM tasks WHERE title LIKE '%[Case]%';").fetchall()
# rows is a list of (id, title, body)
```

For updates, write the new body to a temp file and use a parameterized query — never inline shell quoting for multi-line text:

```python
import sqlite3, os

body = """...full updated card body..."""
db = sqlite3.connect(os.path.expanduser('~/.hermes/kanban.db'))
db.execute("UPDATE tasks SET body = ? WHERE id = ?", (body, 't_<card-id>'))
db.commit()
db.close()
```

## Chaser bump rule during scan

If **no missed reply** is found after the cross-check:
- Compare today against `Chaser due:` on the card.
- If overdue: bump forward **2 days**. Append a History entry: `YYYY-MM-DD  Reviewed: no missed replies. Chaser bumped to YYYY-MM-DD`.
- If not yet due: only bump if this is a scheduled review and the previous bump was more than 2 days ago. (Rolling 2-day extensions are acceptable; the field is advisory, not contractual.)
- If new inbound WAS found, reset `Chaser due:` to **7 days from today** or to the expected response horizon.

## Copy-pasteable case-scan skeleton (Python, execute_code)

```python
import json

# --- AgentMail check ---
# results = mcp_agentmail_list_threads(inboxId="[assistant-email]", after="...", limit=20)
# scan results for vendor-sender threads with "received" label

# --- Gmail check ---
# Run terminal command:
#   $PYTHON_BIN scripts/google_api.py gmail search "from:(...) after:YYYY/MM/DD" --max 20
# If candidate found:
#   $PYTHON_BIN scripts/google_api.py gmail get "<msg_id>"

# --- Decision ---
# missed = bool(candidate_threads)  # define your own filter
# if missed:
#     print("MISSED_REPLY_FOUND: ...")
# else:
#     print("CLEAR: no new inbound")
```