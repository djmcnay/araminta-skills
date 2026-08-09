# AgentMail Webhook Prompt Pattern

Created: 2026-05-18
Context: Timemore scale RMA case — webhook existed but delivered to Discord with a generic prompt. the user wanted WhatsApp delivery with cross-referenced context and an actionable plan, not a notification to check Discord.

## The Prompt Structure That Works

A good AgentMail webhook prompt must do more than "here's an email, triage it." It must:

1. **Identify which open case the email belongs to** — include thread IDs, parties, and context
2. **Cross-reference other threads** for related messages
3. **Consider the user's goal** (not just "process this email" but "the user wants a working scale")
4. **Draft a plan internally** but **surface the actionable information to the user first**
5. **Deliver to WhatsApp** with the fix/answer upfront, not the narrative wrapper

## Key Rules

### Lead with the answer, not the context (the user corrected this twice in one session)
- When a vendor reply contains concrete steps the user can execute: put those steps FIRST
- No "🇨🇳 Timemore replied" preamble — just the reset procedure
- Context (who from, caveats, follow-up needed) goes AFTER the fix

### WhatsApp delivery is a first-class webhook target
- `--deliver whatsapp` works natively — `whatsapp` is in the `_BUILTIN_DELIVER_PLATFORMS` set in `gateway/platforms/webhook.py`
- No cron/polling fallback needed
- The old skill claim that "whatsapp is not supported by the webhook adapter" is outdated

### Never create a polling cron as a webhook substitute
- If a webhook exists but you're not getting deliveries: diagnose it (check gateway logs, test the subscription, verify AgentMail's webhook config)
- If no webhook exists: create one
- Polling is a crutch for a broken trigger path — fix the trigger

### Prompt must reference case context
- Include thread IDs so the agent can `mcp_agentmail_get_thread()`
- Name the parties (Sandy, Chloe) and what each thread covers
- Tell the agent to cross-reference before replying

## Example: Timemore agentmail webhook

Created with:
```
hermes webhook subscribe agentmail \
  --prompt 'An email has just arrived at [assistant-email] from {message.from} with subject: {message.subject}.

You are handling a known open case: the **Timemore Black Mirror Mini scale** stuck in a boot loop. The user (the user) purchased this on eBay. There are TWO active threads with Timemore support:
1. Sandy — calibration-mode thread (threadId: c5454780-0971-417b-899c-1eb400b5f2a0)
2. Chloe — initial-contact thread (threadId: bbe12778-9800-481f-bf98-f4a5e9075711)

YOUR JOB:
1. Read the email content using mcp_agentmail_get_thread().
2. Classify it.
3. Cross-reference the OTHER thread for related messages.
4. Consider the objective: the user wants a WORKING SCALE.
5. Draft a reply in your head (do NOT send it yet).
6. **WhatsApp the user** with a brief summary of who replied, what they said, your proposed response, and anything the user needs to decide.
Do NOT mention eBay unless absolutely necessary.

Use skills: email-policy for reply handling rules.' \
  --events message.received \
  --description "AgentMail inbound — triggers WhatsApp notification with cross-referenced case context and response plan" \
  --deliver whatsapp \
  --skills email-policy
```

Note: the `--secret` returned at creation time is NOT printed — capture it from the CLI output if the service needs to configure it on their end. For AgentMail, the secret goes into their webhook settings as the signing secret.
