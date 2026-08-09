---
name: email-triage
description: Strict policy for triaging a user's personal Gmail. Zero-deletion, filing, and voucher preservation. Companion to email-policy.
version: 2.0.0
author: djmcnay
tags: [admin, email, gmail, triage]
---

# Personal Email Triage Policy

## 1. Excluded Mail (Immediate Skip)
**SKIP** any email where (Sender is the user) AND (Recipient is the user).
Configure the user's email addresses. Examples:
- `user@gmail.com`
- `user@employer.com`
- `user@university.edu`

## 2. Filing and Deletion Rules
- **ZERO DELETION:** Never call `delete` or `trash`.
- **FILING:** Move suspected junk/marketing to a designated label (e.g. `assistant-box`). This is a "proposed bin" for the user's review.

## 3. Classification Matrix

| Category | Description | Action |
| :--- | :--- | :--- |
| **A. External user** | User to Other / Other to user (Intentional) | Surface only if actionable. |
| **B. Human** | Actual person to user | **KEEP.** Draft reply then Surface. Never auto-send. |
| **C. Operational** | Codes, receipts, alerts, **Vouchers** | **KEEP.** Surface key fact/code immediately. |
| **D. Editorial** | Newsletters, blogs, digests | Summarise to digest file. Mark read. |
| **E. Marketing** | Promos, generic pitches, junk | **MOVE to filing label.** |
| **F. Suspicious** | Phishing, credential requests, urgent payment | **KEEP.** Surface as suspicious. Do not click/action. |

**Marketing Exceptions (Treat as Category C):**
- Any email containing a **voucher code** or **promo code**.

## 4. Processing Loop (Strict Sequence)

1. **Excluded Check:** If (Sender is user) AND (Recipient is user) then **STOP**.
2. **Pre-Flight Dependency Check:**
   - **Load** `email-policy` skill (for the shared case-handling workflow).
   - **Verify** the task board is reachable (cases live as case-prefixed cards).
   - **FAIL-SAFE:** If the task board is inaccessible, **STOP immediately** and surface a high-priority alert: *"Critical Error: Cannot access case system. Triage suspended to prevent loss of context."*
3. **Case Matching:** Using the task board, check if the email matches an open case card.
   - If match: Bind to case, include Case ID/Status in output, update the card body and post a comment.
4. **Fetch Content:** Read full body if required for classification.
5. **Classify:** Assign Category A-F.
6. **Execute Action:**
   - Cat E: Move to filing label.
   - Cat B: Draft then Surface.
   - Cat F: Surface as suspicious.
7. **Channel Decision:**
   - Priority 1: Explicit directive in email.
   - Priority 2: **Default channel** (configure per your setup — WhatsApp, Telegram, etc.).
   - Priority 3: **Backup channel** (Discord, etc.).
8. **Finalize:** Mark as read.

## 5. Output Contract

- **Correspondence:** `Sender` then `Context` then `Draft`.
- **Operational/Voucher:** `Key Fact/Code` then `Context`.
- **Suspicious:** `Suspicious email from [Sender] regarding [Topic]. No action taken.`
- **Cron Mode:** If no items surfaced then output **MUST** be exactly `NO_REPLY`.

## 6. Hard Rules
- **No Auto-Send:** All third-party replies are draft-only.
- **Data Privacy:** Use placeholders (`{address}`, `{account_number}`) in all drafts.
- **Case Priority:** Case card matches override all other triage logic.
- **Dependency Mandate:** Triage must never occur without a verified load of the case system.