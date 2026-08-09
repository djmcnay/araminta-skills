---
title: AgentMail Blocked → Gmail Identity Flip
updated: 2026-05-19
skill: email-policy
---

# When AgentMail Is Blocked by a Vendor

## Trigger
Remote MTA rejects outbound from `[assistant-email]` with a spam/content filter error, typically:
- `554 Reject by content spam`
- `550 blocked`
- Repeated delivery failures to the same domain from the same agentmail source

## Pitfall
Continuing to retry from the same blocked source address is futile — the MTA has explicitly rejected the identity. Every bounce consumes AgentMail quota and pollutes the inbox with NDR noise.

## Procedure
1. **Forward the email chain** to `[user-email]` using `forward_message` with a descriptive subject line (e.g. "FW: Vendor X — thread re: topic"). This gives the user full context in his Gmail.
2. **Draft the reply in the user's Gmail** using the google-workspace skill:
   - Use `$GAPI gmail send --to ... --subject ... --body ...` (or `--html` if needed)
   - **But do NOT execute the send.** Treat this as a draft-only operation.
3. **Identity flip**: the email must be authored/signed as **the user**, not Araminta.
   - First-person voice: "I'm writing to..."
   - Sign-off: "Best regards, [user-name]"
   - Never mention "My assistant" or "Araminta" in the body, unless the context genuinely requires it
4. **Get explicit approval.** Present the full draft text to the user with: "Your call — approve, edit, or reject?" No shorthand. No assumption of implied consent.
5. **Only after the user says yes**, execute the send from Gmail.

## Rationale
the user's mail originates from a Gmail domain with established reputation (dkim, spf, dmarc, history) and is far less likely to be blocked as spam than an `@agentmail.to` address that the vendor has never heard of. Sending as himself also keeps the legal attribution correct.

## Cross-reference
- See `references/bounce-recording-procedure.md` for how to record bounce events in the kanban case card
- See `references/cron-reply-watchdog.md` for monitoring vendor replies after the send
