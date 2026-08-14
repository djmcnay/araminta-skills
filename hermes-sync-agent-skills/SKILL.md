---
name: hermes-sync-agent-skills
description: Use when backing up reviewed agent-authored local skills safely.
ownership: collab
---

# Hermes Sync Agent Skills

Use this skill to make a reviewable backup of local, genuinely agent-authored Hermes skills into `skills/agent-authored/` in an Araminta profile distribution. It is deliberately conservative: it is a copy-out workflow, never an installer, and it does not modify `~/.hermes/skills`.

## Safety contract

- Do not scan for, infer, or automatically select skills. Only manifest entries are eligible.
- Add an entry only after a human has established that it was authored locally by an agent. Never list official bundled skills, hub/tap-installed skills, external-directory skills, archives, or skills of unknown provenance.
- A manifest entry needs `origin: "agent-authored-local"`, non-empty `reviewed_by` and `review_note` fields, and one simple directory name. That declaration is an auditable human assertion, not a provenance detector.
- Sources must be real direct children of `source_skills_root`. Source trees with any symlink are rejected. The backup uses ordinary copied files, never symlinks.
- Begin every change with a dry run. Normal runs only copy or update files from selected sources; they never remove an existing destination tree or delete stale destination files.
- Retiring a backup is exceptional: use a separately reviewed `retire` manifest entry and both `--prune` and `--allow-delete`.

## Files

```
hermes-sync-agent-skills/
  SKILL.md
  config.example.json                 # portable path placeholders
  agent-authored-manifest.example.json
  scripts/sync_agent_authored_skills.py
  tests/test_sync_agent_authored_skills.py
```

Create a local `config.json` by copying the example. It is gitignored. Point it at the local Hermes skills directory and the desired Araminta distribution path, for example the distribution's `skills/agent-authored` directory. Keep paths machine-specific only in this local file. The manifest can be a local file alongside `config.json`, or a checked-in reviewed artifact when appropriate; `manifest_path` may be absolute or relative to the config file.

## Manifest review

Start from `agent-authored-manifest.example.json`. Each selected skill needs a clear review note stating why it is agent-authored and why it is not from a bundle, hub, tap, external directory, or archive. The script copies no directory not named here, even if it is located under the configured Hermes root.

Before execution, review:

1. Every name and provenance assertion in the manifest.
2. The configured destination is the intended `skills/agent-authored` directory in the Araminta distribution.
3. The dry-run output: each `COPY source -> destination` line and any proposed `DELETE` line.

## Commands

Run a dry run first:

```bash
python3 scripts/sync_agent_authored_skills.py --config config.json --dry-run
```

After approving exactly that plan, copy:

```bash
python3 scripts/sync_agent_authored_skills.py --config config.json
```

Normal sync does not delete stale backups. To remove one, place only its simple name in `retire`, review the dry run, then use the two explicit acknowledgements:

```bash
python3 scripts/sync_agent_authored_skills.py --config config.json --prune --allow-delete --dry-run
python3 scripts/sync_agent_authored_skills.py --config config.json --prune --allow-delete
```

The tool refuses unsafe names, duplicate selections, missing reviews, wrong provenance assertions, nonexistent sources, symlinked source trees, and symlinked destinations. It never writes to the configured source root.

## AI-agent operating notes

An AI agent must not add skills to the manifest based on directory names, timestamps, content guesses, or a Hermes listing. Ask the maintainer for an explicit provenance decision if a skill is not already known to be agent-authored. Do not create `config.json` with personal paths in a commit, and do not place credentials or tokens in configuration, manifests, or copied skill content.

The script's output is deterministic: selected copies and retirements are name-sorted. Treat the dry-run output as the change request. If it contains an unexpected path, stop rather than editing roots or bypassing the checks.

## Developer notes and verification

The script uses only Python's standard library. Its module docstring describes purpose, architecture, intent, and use. Tests use temporary directories and cover explicit selection (including an unselected official-looking directory), dry-run no-write behavior, ordinary copied files, symlink rejection, and deletion's double opt-in/no-delete default.

Run:

```bash
python3 -m unittest discover -s tests -v
```
