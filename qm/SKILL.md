---
name: qm
description: Invoke QM (Quartermaster) — a non-blocking Codex CLI sub-agent. Fires a background terminal process, returns immediately, notifies Minty when done. Use for building features, debugging, refactoring, and multi-file changes.
ownership: collab
version: 2.3.0
author: Minty + David
license: MIT
metadata:
  hermes:
    tags: [Coding-Agent, Codex, Background, Non-Blocking, Refactoring, Autonomous]
    homepage: https://github.com/NousResearch/hermes-agent
    related_skills: [codex, claude-code]
---

# QM — Quartermaster

QM runs OpenAI Codex CLI (`codex exec`) as a **background terminal process**. Minty fires it off and is free immediately. When QM finishes, Hermes auto-notifies Minty — no polling, no blocking.

**QM never addresses David.** All output lands in a result file that Minty reads on notification.

> **As of May 2026: switched from Claude Code to Codex CLI.** Codex is installed at `/usr/bin/codex` (v0.131.0+).

---

## When to Use QM

| Use QM | Do it yourself |
|--------|----------------|
| Building a new feature (multi-file) | Single-line fix |
| Debugging a complex failure | Quick read + edit |
| Multi-file refactor (5+ files, 200+ lines) | A single-file patch under 50 lines |
| Validation pass on a new skill or schema | Typo / docs / changelog edits |
| Anything where gpt-5.5 (or the smartest available model) is materially better than the current model | A trivial verify step |

Per David (9 Jun 2026): *"GPT 5.5 is better at coding than Minimax3"* — so when the orchestrator is running on a cheaper model and the work is a multi-file refactor, fan it to QM (a background Codex task on gpt-5.5) rather than executing inline. The `kanban-orchestrator` skill's "you could do it yourself, so do it" trap covers the why; this skill covers the how.

The default model for QM is the smartest available, typically `gpt-5.5`. Do NOT substitute a cheaper model unless the task is genuinely trivial — the whole point of QM is that the smart model catches things the cheap model misses. If the cheapest model would do, do the work yourself; do not waste a Codex call on it.

Codex v0.131.0+ does **not** have a `-p` / `--print` quiet flag. In v0.131+:
- `--dangerously-bypass-approvals-and-sandbox` already puts Codex into non-interactive execution mode (it runs the prompt, prints output, and exits — no TTY needed).
- Adding `-p` causes Codex to fail immediately with `error: a value is required for '--profile <CONFIG_PROFILE>' but none was supplied` because in v0.131+ `-p` is short for `--profile` (a config-profile selector), not print/quiet mode.

**Do NOT pass `-p`.** Output is captured to a timestamped file via the `>` shell redirect at the end of the command.

When the process finishes, Hermes notifies Minty. Read the result file and relay the relevant parts to David.

---

## Standard Invocation

```python
terminal(
  command="""SHELL=bash codex exec "PROMPT HERE" --dangerously-bypass-approvals-and-sandbox > /tmp/qm_result_$(date +%s).txt 2>&1""",
  background=True,
  notify_on_complete=True,
)
```

When the process finishes, Hermes notifies Minty. Read the result file and relay the relevant parts to David.

**Do NOT use `-p`** — in Codex v0.131.0+, `-p` means `--profile` (configuration profile), not quiet mode. Omit it entirely; `--dangerously-bypass-approvals-and-sandbox` already puts Codex into non-interactive execution mode.

When the process finishes, Hermes notifies Minty. Read the result file and relay the relevant parts to David.

---

## Prompt Guidelines

The prompt passed to `codex exec` is QM's **only** source of information — always include:

- **Absolute file paths** to relevant files (QM starts with a blank slate)
- **Error messages** verbatim (copy from logs)
- **Project root** and test command
- **Constraints** (don't break the API, keep backwards compat, run tests after)
- **What's already been tried** if this is a retry

Add this to the end of every prompt:

> When done, write your report in this format:
> TASK: what you were asked to do
> DONE: what you actually did
> CHANGED: files created or modified (with brief reason)
> VERIFIED: tests run / commands used to confirm
> ISSUES: anything unexpected, or follow-up needed
> FOR DAVID: one plain-English sentence Minty can relay to David

---

## Example: Fix a Bug

```python
terminal(
  command="""SHELL=bash codex exec "
You are QM (Quartermaster), a methodical coding sub-agent for Araminta. Never address David. Return a TASK/DONE/CHANGED/VERIFIED/ISSUES/FOR DAVID report.

TASK: Fix the JWT validation failure in the auth module.

CONTEXT:
Error: jwt.exceptions.InvalidSignatureError: Signature verification failed
File: /home/djmcnay/.hermes/hermes-agent/auth/jwt_validator.py, line 83
Project root: /home/djmcnay/.hermes/hermes-agent/
Test command: cd /home/djmcnay/.hermes/hermes-agent && source .venv/bin/activate && pytest tests/auth/ -q
Note: JWT secret was rotated last week — suspect validator is reading a hardcoded fallback key.

When done, write your report in this format:
TASK: what you were asked to do
DONE: what you actually did
CHANGED: files created or modified (with brief reason)
VERIFIED: tests run / commands used to confirm
ISSUES: anything unexpected, or follow-up needed
FOR DAVID: one plain-English sentence Minty can relay to David
" --dangerously-bypass-approvals-and-sandbox > /tmp/qm_result_$(date +%s).txt 2>&1""",
  background=True,
  notify_on_complete=True,
)
```

## Example: Build a Feature

```python
terminal(
  command="""SHELL=bash codex exec "
You are QM (Quartermaster), a methodical coding sub-agent for Araminta. Never address David. Return a TASK/DONE/CHANGED/VERIFIED/ISSUES/FOR DAVID report.

TASK: Add a /status endpoint to the Honcho API that returns container health.

CONTEXT:
Project root: /home/djmcnay/honcho/ (Docker Compose stack)
Router files: /home/djmcnay/honcho/src/routers/ — follow the pattern in sessions.py
Test command: cd /home/djmcnay/honcho && pytest tests/ -q
Endpoint: GET /status → {\\\"postgres\\\": \\\"ok|err\\\", \\\"redis\\\": \\\"ok|err\\\", \\\"deriver\\\": \\\"ok|err\\\"}
Check each service with a lightweight ping (SELECT 1 for postgres, PING for redis).

When done, write your report in this format:
TASK: what you were asked to do
DONE: what you actually did
CHANGED: files created or modified (with brief reason)
VERIFIED: tests run / commands used to confirm
ISSUES: anything unexpected, or follow-up needed
FOR DAVID: one plain-English sentence Minty can relay to David
" --dangerously-bypass-approvals-and-sandbox > /tmp/qm_result_$(date +%s).txt 2>&1""",
  background=True,
  notify_on_complete=True,
)
```

---

## Flags Reference

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--dangerously-bypass-approvals-and-sandbox` | No interactive prompts, no sandbox; runs in print mode (no TTY needed) |
| `> /tmp/qm_result_$(date +%s).txt 2>&1` | Capture all output to timestamped file |

> **Removed flag:** Codex v0.131.0+ interprets `-p` as `--profile` (configuration-profile selector), not quiet/print mode. Passing `-p` without `--profile <name>` fails with `error: a value is required for '--profile <CONFIG_PROFILE>'`. Omit it entirely; `--dangerously-bypass-approvals-and-sandbox` already provides non-interactive execution.

For read-only investigation: omit `--dangerously-bypass-approvals-and-sandbox` and use a narrower prompt.

---

## On Notification

When Hermes notifies Minty that QM has finished:

1. **Pick up the latest result file** — the timestamp suffix prevents collisions if multiple QM tasks ran:
   ```bash
   RESULT=$(ls -t /tmp/qm_result_*.txt 2>/dev/null | head -1)
   cat "$RESULT"
   ```
   Never guess the filename from the process session id; the shell redirect writes a fresh `$(date +%s)` name on every run.
2. Extract the **FOR DAVID** line — relay this to David
3. Check **ISSUES** — flag anything that needs follow-up
4. Optionally run the test command to verify QM's claims
5. **If the work touched a model alias or provider route**, run the three-step smoke test in [`references/model-route-verification.md`](references/model-route-verification.md) before declaring success. The silent-OAuth-fallback trap can make a "working" alias produce responses from a completely different model.

---

## Rules

1. **Always include absolute paths** — QM has zero context from the conversation
2. **Always redirect output** to `/tmp/qm_result_$(date +%s).txt 2>&1` — the timestamp prevents collisions if multiple QM tasks run
3. **Always add the report format to the prompt** — Codex needs the structure, it won't default to the same format as Claude
4. **Set `SHELL=bash`** — Codex may need a bash environment for subshell expansion
5. **Don't chain QM tasks immediately** — wait for notification before firing the next one if they depend on each other
6. **Verify QM's work** — read the diff or run the tests; summaries can omit details
7. **If QM fails twice on the same task** — diagnose yourself before delegating again

---

## Reference: model-route verification

When QM's work added, removed, or modified a `model_aliases` entry, a `provider`, or a `base_url` in `config.yaml`, don't trust a "successful" smoke test on the response text alone. Run [`references/model-route-verification.md`](references/model-route-verification.md) — covers the silent-fallback trap, a three-step verification protocol (clear logs → identity probe → log forensics), and recovery steps for expired OAuth.

---

## QM in an orchestrator-driven flow

When the orchestrator is the calling agent (the one that just fanned a parent card and is deciding what to do next), QM is the right delegate for any code-heavy child task. Pattern:

1. Orchestrator creates the parent card (e.g. `[Project-] rental-search refactor`).
2. Orchestrator creates child cards for each subtask: commit, push, cron registration, test sweep. Assigns code-heavy ones to `qm`, communication ones to `araminta` (or `minty`).
3. Orchestrator frees up. The dispatcher claims the `qm` children and fires background Codex calls.
4. When each child completes, the orchestrator reads the QM result file and reports back to David.

The orchestrator does NOT execute the work itself, even if it could. The `kanban-orchestrator` skill's anti-temptation rules apply.
