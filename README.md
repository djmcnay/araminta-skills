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
| `amazon` | Browse, shop, and manage returns on Amazon. Reorder past purchases, fuzzy search, best-value unit pricing, product research, basket management, and return initiation. Works with any persistent browser session. |

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

```
<skill-name>/
  SKILL.md              # The skill definition (frontmatter + instructions)
  references/           # Supporting documentation, worked examples, edge cases
  scripts/              # Runnable helpers (where applicable)
  templates/            # Copy-and-modify starters (where applicable)
```

## License

MIT

## Author

Araminta Milland-Wilde (with David McNay)

## Related

- [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs)
- [Skills tap docs](https://hermes-agent.nousresearch.com/docs/user-guide/skills)