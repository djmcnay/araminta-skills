# Case Scan Report Template

## When to use

This template is the canonical output format for scheduled cron case scans (and interactive case scans when the user asks "where are we on everything?"). Use it to produce terse, consistent, scannable summaries of all open cases.

## Template format

```
**Case scan — N open cases reviewed**

**[Case title]**
- Last inbound: DATE
- Missed replies: yes/no (brief cross-check summary)
- [If overdue:] Chaser due WAS drifted (card said X, review said Y). Corrected to Z.
- Action: what happens next and who is waiting

**[Case title]**
- Last inbound: DATE
- Missed replies: yes/no
- [If new inbound found:] What the inbound said (one-sentence summary)
- [If no news:] Chaser bumped to DATE. / No chaser change needed.
- Action: what happens next
...

**Vault drift cleanup:** [If applicable] discovered N stale duplicate files across case(s). All overwritten with canonical kanban body.
```

## Field rules

| Field | Rule |
|-------|------|
| Last inbound | Date of the most recent vendor/human reply. If none since case creation, say "None since case opened DATE". |
| Missed replies | Either "No missed replies (AgentMail + Gmail cross-checked: clean)" or briefly name the missed reply source and content. |
| Chaser drift | Include only when the card's `Chaser due:` field and the last review comment disagree. State the corrected value. |
| Action | Must name the next concrete step (e.g. "awaiting the user's approval to send Gmail draft r-XXXX", "the user to reply with video", "awaiting vendor's next reply") and who is blocking it. |
| Vault drift | Include only if you found and fixed stale/duplicate vault files during the scan. |

## Length target

- Whole report ≤ 30 lines per case.
- No more than 2 sentences per sub-bullet.
- the user scans this on WhatsApp between meetings — brevity is the point.

## What NOT to include

- Full email body text.
- Multi-step historical narratives inside each section.
- Any "nothing to report" blather — if nothing changed, case scan output should be `[SILENT]` per invocation mode rules.
- Links to thread IDs or message IDs (the user doesn't use them).
- References to previous cron run numbers or agent session IDs.

## Example (good)

```
**Case scan — 3 open cases reviewed**

**Discovery Insure — remove Mazda 2018 (Classic Plan 4003980217)**
- Last inbound: 10 Apr 2026
- Missed replies: no (AgentMail + Gmail cross-checked)
- Chaser was drifted (card said 2026-05-21, review said 2026-05-23). Corrected to 2026-05-23
- Action: still awaiting your approval to send Gmail draft

**Discovery Health — cancel membership 846628082**
- Last inbound: 10 Apr 2026
- Missed replies: no (cross-check clean)
- Chaser was drifted (card said 2026-05-28, review said 2026-05-23). Corrected to 2026-05-23
- Action: still awaiting your approval to send Gmail draft

**Timemore Black Mirror Mini — scale failure / RMA**
- Confirmed inbound: Chloe replied 20 May via ticket thread (acknowledged 554 block, requested video + order number — same ask as prior). the user already sent videos + photo from Gmail on 20 May. AgentMail remains completely blocked by Timemore.
- Also detected: the user's Gmail CC 20 May still showing unread in AgentMail inbox (thread d3e28…). Duplicate of direct exchange. update_message returned 404 — state logged in kanban comment.
- Updated card body with full history. Awaiting Timemore's next reply.
```
