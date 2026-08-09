# Bounce Recording Procedure

## SMTP bounce types

### Transient (temporary) bounces
- `450`, `451`, `452` — recipient server busy, try again later
- `421` — service not available, channel closing
- Action: resend after some time. Mark in case history as pending redelivery.

### Permanent (hard) bounces
- `550`, `551`, `552`, `553`, `554` — message permanently rejected
- `554 5.7.1` — relay denied / not authorised
- **`554 Reject by content spam`** — recipient MTA classified the message as spam. This is a **permanent block** from that server, not a transient issue. Resending from the same source address/domain will produce the same result.
- Action: do NOT resend from the same source. Flag to the user as "AgentMail source blocked by [recipient domain] — need alternative delivery path (Gmail, their ticket system, etc.)."

## Case study: Timemore EU (hello@timemore.com)
- Aliyun-hosted mail server classifies all AgentMail (Amazon SES) outbound as spam
- Two attempts both returned `554 Reject by content spam`
- Resolution: forward the reply into Chloe's existing thread (same domain, different support agent) and explain the bounce
- If Chloe's also bounces, escalate to using their web ticket system or the user's Gmail directly

## Procedure when bounce detected
1. Extract Final-Recipient and Diagnostic-Code from the bounce notification
2. Cross-reference against open kanban cases — does the recipient match a Participants address?
3. Update kanban card:
   - Add constraint: "[domain] rejects mail from AgentMail — alternative delivery required"
   - Add step: "[ ] Re-send to [recipient] — bounced ([error code]). Need alternative delivery."
   - Append to History with bounce context
   - Post a kanban comment
4. Do NOT treat the bounce as a reply from the vendor
5. Do NOT mark the outbound as "sent and awaiting reply"
6. Flag to the user with: who bounced, what the MTA said, what the roadblock means
