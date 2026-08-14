# araminta-skills

A collection of portable agent skills, installable via the Hermes Agent skills tap mechanism. Designed to be harness-agnostic: the SKILL.md format is a plain markdown contract that any AI agent with browser tools can follow.

## Install (Hermes Agent)

```bash
hermes skills tap add djmcnay/araminta-skills
hermes skills search --source github
hermes skills install amazon
```

Or install everything:

```bash
hermes skills tap add djmcnay/araminta-skills
hermes skills update
```

## Skills

| Skill | Description |
|-------|-------------|
| `araminta-amazon` | Browse, shop, and manage returns on Amazon. Reorder past purchases, fuzzy search, best-value unit pricing, product research, basket management, and return initiation. Works with any persistent browser session. |
| `train-line` | API-first UK rail information: National Rail Darwin live departures and arrivals, read-only journey-link generation, and SWR JourneyCheck fallback. Customise only local deployments with environment-specific station aliases. |
| `email-policy` | Policy for an AI assistant's own email inbox. Classify inbound, decide reply channel, case-match against a task board, draft-not-send. Works with AgentMail or similar. |
| `email-triage` | Strict policy for triaging a user's personal Gmail. Zero-deletion, filing, voucher preservation, case matching. Companion to email-policy. |
| `formal-contract-drafting` | Draft clean, fully populated formal agreements from scratch. Tenancy agreements, side letters, contracts. Markdown to PDF/HTML/RTF pipeline. No templates needed. |
| `beanz-shopping` | Browse and compare Beanz UK coffee through the public Algolia catalogue. Account and purchase activity lives in the private `beanz-buying` skill. |
| `price-spy` | Price watchlist. Track products across retailers, alert on price drops, stock changes, and availability. Amazon, Shopify, and generic scraping. Cron-friendly silent mode. |
| `araminta-research` | Multi-agent research pipeline for product evaluation, academic literature review, and general web research. Spawns parallel subagents for data collection, analysis, hallucination verification, and structured reports. |
| `social-media-tracker` | Track YouTube/social channels, collect new posts, extract metadata/transcripts with yt-dlp and fallback workflows, and produce concise digests. |
| `retrieve-redacted-secrets` | Safely retrieve or transfer redacted local credentials when platform output filters obscure required values. Includes auth-state injection patterns. |
| `nordvpn` | Control NordVPN on a host machine via the native CLI, with status/connect/disconnect helpers and killswitch safety guidance. |
| `hermes-sync-agent-skills` | Autonomously review and back up clearly marked local agent-authored skills into an Araminta profile distribution, with a local commit. |

More skills will be added as they are genericised from the araminta-toolshed.

## Philosophy

The SKILL.md format is a plain markdown contract. It describes *what to do* and *how to do it* in terms any agent can follow. It does not depend on Hermes-specific tool names, user-specific paths, or persona-specific context.

Skills here are genericised versions of real production skills:
- User names replaced with "the user"
- Personal addresses/postcodes replaced with placeholders
- Harness-specific tool names described by function, not by API name
- Configuration values (CDP ports, browser profiles) described as patterns to adapt

The source of truth for each skill is this repo. Local copies are deployments.

## Structure

Hermes taps resolve skills from the repository's `skills/` directory. Every installable package therefore lives under that directory:

```
skills/
  <skill-name>/
    SKILL.md            # The skill definition (frontmatter + instructions)
    references/         # Supporting documentation, worked examples, edge cases
    scripts/            # Runnable helpers (where applicable)
    templates/          # Copy-and-modify starters (where applicable)
    items.json          # Data files (where applicable, e.g. price-spy watchlist)
```

This layout is intentional. Do not move installable skills back to repository root: a registered Hermes tap uses `skills/` as its source path.

## License

MIT

## Author

Araminta Milland-Wilde (with contributors)

## Related

- [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs)
- [Skills tap docs](https://hermes-agent.nousresearch.com/docs/user-guide/skills)