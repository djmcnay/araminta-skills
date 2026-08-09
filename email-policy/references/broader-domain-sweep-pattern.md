---
title: Broader Domain Sweep for Case-Scan Cross-Checks
updated: 2026-05-20
skill: email-policy
---

# Broader Domain Sweep Pattern

## The problem

Vendors — especially banks, insurers, and large enterprises — send operational notifications, auto-reminders, and pre-inspection requests from sub-addresses (`notifications@`, `noreply@`, `alerts@`, `emailhub.*@`) that **do not** appear in the human `Participants:` list on the case card.

Searching only explicit participant addresses misses these. In a real case-scan session (20 May 2026), a participant-only search for `from:(insuremaintenance@discovery.co.za OR insureinfo@discovery.co.za)` returned **zero** new results since the last scan. A broader domain sweep `from:discovery.co.za after:2026/05/14` revealed a missed operational email: `InsureNotifications@discovery.co.za` sent a pre-inspection requirement for plan 4003980217 on **15 May**, proving the Mazda 2018 was still on the policy despite a removal request sent 9 April.

## The fix

Every confirmed inbound scan must now run **two Gmail searches**:

### 1. Participant-specific search
```bash
PYTHON_BIN="$HOME/.hermes/hermes-agent/.venv/bin/python"
$PYTHON_BIN ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py \
  gmail search "from:(participant1@domain.com OR participant2@domain.com) after:YYYY/MM/DD" --max 20
```

### 2. Broader domain sweep
```bash
PYTHON_BIN="$HOME/.hermes/hermes-agent/.venv/bin/python"
$PYTHON_BIN ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py \
  gmail search "from:domain.com after:YYYY/MM/DD" --max 20
```

**When the domain sweep returns a different service line from the same parent company** (e.g. Discovery Health AGM vs Discovery Insure pre-inspection), match using:
- The plan/policy/contract number in the subject line or body (e.g. plan **4003980217**)
- Keywords in the subject line (e.g. "pre-inspection", "vehicle")
- Then route to the correct case.

## Classification of auto-notifications

Auto-reminders, pre-inspections, and similar automated messages are **not** human replies, but they are **actionable** when they confirm the original request was ignored. Example: a pre-inspection requirement for a sold vehicle proves the vehicle removal request is unprocessed.

Actions on finding one:
1. Surface to the user immediately: what the notification says, and what it implies about the case.
2. Update kanban card (History, Notes, Latest summary) — flag urgency, do **not** reset `Chaser due:`.
3. Mirror update to vault.
4. Post a kanban comment.
5. This does **not** reset chaser dates — it *accelerates* the deadline.

## Real vendor address patterns (Discovery)

Discovery Insure / Health uses at least the following from-addresses for the same account:
- `insuremaintenance@discovery.co.za` — human/ops contact
- `insureinfo@discovery.co.za` — general info
- `InsureNotifications@discovery.co.za` — auto-reminders, pre-inspections
- `noreply@discovery.co.za` — system confirmations
- `yourhealth@emailhub.discovery.co.za` — health scheme marketing / AGM notices

This list is illustrative. For any bank, insurer, or telco, always default to the broader domain sweep rather than trusting the participant list to be exhaustive.

## Trigger

Load this pattern when:
- Running a confirmed inbound scan for any vendor case.
- The vendor domain matches a known multi-service enterprise (bank, insurer, telco, utility).
- The previous participant-only search returned clean but the case still feels stalled.
