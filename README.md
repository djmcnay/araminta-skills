# araminta-skills

A curated collection of portable [Hermes Agent](https://hermes-agent.nousresearch.com) skills, installable via the Hermes skills tap mechanism.

These are generic, reusable skills that work for any Hermes user. They contain no user-specific paths, credentials, or persona references. A few may need light adaptation for your environment (noted below).

## Install

Register this repo as a tap source, then install individual skills:

```bash
hermes skills tap add djmcnay/araminta-skills
hermes skills search --source github
hermes skills install <skill-name>
```

Or install everything at once:

```bash
hermes skills tap add djmcnay/araminta-skills
hermes skills update
```

## Skills

| Skill | Description | Portability |
|-------|-------------|-------------|
| `formal-contract-drafting` | Draft clean, fully populated formal agreements (tenancy, side letters, contracts) from scratch using Markdown to PDF/HTML. | Fully portable. |
| `hermes-api-troubleshooting` | Diagnostics and resolution for Hermes API authentication failures (401s), config drift, and provider fallback issues. | Fully portable. |
| `retrieve-redacted-secrets` | Workaround for platform output filters that redact secrets (API keys, passwords) in config files. Includes terminal-based retrieval patterns. | Fully portable. |
| `qm` | Quartermaster: a non-blocking Codex CLI sub-agent pattern. Fires `codex exec` as a background process, returns immediately, notifies on completion. For multi-file coding tasks. | Portable. May need model name adjustment (defaults to gpt-5.5). |
| `browser-display` | Remote browser viewing via TigerVNC + noVNC + Tailscale Funnel. Shows the user a live browser screen over the web. | Portable with adaptation. Configured for Raspberry Pi + Tailscale. Adjust hostname, funnel path, and display number for your setup. |
| `research` | Multi-agent research pipeline for product evaluation, academic literature review, and general web research. Spawns parallel subagents for scraping, runs analysis and hallucination verification, delivers structured reports. | Portable with adaptation. Vault path defaults to `~/Documents/GitHub/araminta-vault/research/`. Adjust for your vault layout. |

## Structure

Each skill is a top-level directory containing:

```
<skill-name>/
  SKILL.md              # The skill definition (frontmatter + instructions)
  references/           # Supporting documentation, worked examples, edge cases
  templates/            # Copy-and-modify starters (where applicable)
  scripts/              # Runnable helpers (where applicable)
  tests/                # Pytest tests (where applicable)
```

## Updating

Tap-installed skills are editable local copies. However, `hermes skills update` will overwrite local edits with the repo version. The intended workflow:

1. Edit the skill in this repo
2. Commit and push to GitHub
3. Run `hermes skills update` on each machine to pull changes

This repo is the source of truth. Local copies are deployments.

## License

MIT

## Author

Araminta Milland-Wilde (with David McNay)

## Related

- [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs)
- [Skills tap docs](https://hermes-agent.nousresearch.com/docs/user-guide/skills)