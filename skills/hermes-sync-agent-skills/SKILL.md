---
name: hermes-sync-agent-skills
description: Autonomously inventory and back up clearly marked local agent-authored Hermes skills into Araminta, with a local distribution commit.
ownership: collab
---

# Hermes Sync Agent Skills

When manually invoked as `/hermes-sync-agent-skills`, autonomously review the local Hermes skill inventory, inspect every automatically eligible candidate's content for portability and secrets, then run the noninteractive apply command. Do not ask David to maintain a manifest or approve individual entries. This workflow backs up only new agent-authored skills into the Araminta distribution and creates a local commit; it never pushes.

`hermes-sync-minty` is the separate, later workflow for fetching, reconciling, and pushing that distribution.

## Automatic ownership contract

New unilateral agent-authored skills must use this exact frontmatter signal in their `SKILL.md`:

```yaml
---
name: example
ownership: agent-authored
---
```

See `templates/agent-authored-skill.example.md` for a portable complete example.

This is the only automatic eligibility signal. Legacy or unmarked skills are reported as `UNKNOWN` for agent review and are never copied. The scanner does not infer ownership from names, timestamps, text, or a Hermes listing.

It deterministically scans direct local entries by name and excludes, with a reported reason: Hermes bundled skills named in configured manifests, hub/tap-installed skills named in configured metadata, configured external directories, archive files, symlinked entries or trees, and obvious secret-like content. Sources and copied output always use ordinary files, never symlinks. The secret check is a guardrail, not a substitute for inspecting eligible content before applying.

## Local configuration

Copy `templates/config.example.json` to local `config.json`; it is ignored by Git. Use only portable placeholders in examples and never commit machine paths, tokens, credentials, or private values. The configured `araminta_checkout` must be the top level of a real Git checkout, and `destination_agent_authored_root` must resolve within it.

Supply any available Hermes bundled manifests in `bundled_manifest_paths`, hub/tap metadata in `hub_metadata_paths`, and every external source root in `external_skill_dirs`. The scanner accepts one path or an array for each metadata field and conservatively extracts ordinary names from common metadata schemas. Omit an unavailable metadata source rather than guessing its contents.

## Autonomous workflow

First inventory the source:

```bash
python3 scripts/sync_agent_authored_skills.py --config config.json --inventory
```

For each `ELIGIBLE` entry, inspect its files: verify it is genuinely unilateral agent work, portable, and contains no secrets or machine values. `EXCLUDED` and `UNKNOWN` entries remain untouched. Then preview and apply:

```bash
python3 scripts/sync_agent_authored_skills.py --config config.json --apply --dry-run
python3 scripts/sync_agent_authored_skills.py --config config.json --apply
```

Apply copies only eligible skills, does not delete stale distribution trees, stages only paths changed by that run, and creates one local Git commit only when there is a change. It refuses symlinked paths, a non-Git checkout, a destination outside the checkout, and an already-dirty destination. It never runs a push command.

## Developer verification

The implementation uses only the Python standard library. Its module docstring records its purpose, selection architecture, and safety boundary. Tests use temporary Git repositories and cover automatic eligibility, metadata/external/archive exclusions, unknown unmarked skills, dry-run no-write, copy plus commit, no-change no-commit, symlink rejection, and no deletion by default.

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/sync_agent_authored_skills.py
git diff --check
```
