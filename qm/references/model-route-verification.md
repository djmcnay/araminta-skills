# Model-Route Verification — The Silent-Fallback Trap

When a Hermes alias or provider route appears to work but actually fell through to a fallback, the response text alone is insufficient evidence. This reference captures the trap and the three-step protocol to detect it.

## The trap

Hermes's `fallback_providers` chain (configured in `model.fallback_providers` in `config.yaml`) silently catches any primary-provider failure, including expired OAuth tokens. The user sees a successful-looking response; the response is from a completely different model.

**Real example from this session:** A smoke test for the newly-added `nous/nemotron-3-ultra` alias returned "I was trained by OpenAI, and my name is Miss Araminta Milland-Wilde" — looks fine, but the agent log showed:

```
WARNING cli: Primary provider auth failed (Hermes is not logged into Nous Portal.).
Falling through to fallback: openai-codex/gpt-5.4-mini
```

The "OpenAI" answer was GPT-5.4-mini echoing the test prompt through a persona system prompt. The 60-day-expired Nous OAuth token was the root cause; the silent fallback hid it.

**Which providers are vulnerable:** any OAuth-backed provider where the access token can expire without an obvious user-facing signal. Confirmed: Nous Portal (`nous` provider), OpenAI Codex (`openai-codex`), GitHub Copilot (`copilot`). API-key providers (OpenRouter, Gemini, xAI) fail loudly on a bad key, so the trap is less likely to bite there.

## Three-step verification protocol

Use this whenever you change a model alias, add a new provider, or suspect auth is stale. Each step is cheap; together they make silent-fallback detection routine.

### 1. Pre-test: clear logs and set a timestamp baseline

```bash
: > ~/.hermes/logs/agent.log
: > ~/.hermes/logs/gateway.log
date +%s > /tmp/smoke_baseline_$$
echo "smoke baseline: $(date)"
```

The `$$` suffix lets multiple smoke tests in the same session coexist without clobbering each other.

### 2. Identity probe

Pick a question whose correct answer is distinctive to the target model. Useful probes by family:

| Target model | Probe question | Expected signal in response |
|---|---|---|
| NVIDIA Nemotron (any) | "Which organisation trained you, in one line?" | "NVIDIA" |
| OpenAI GPT (Codex) | "In one line, who trained you?" | "OpenAI" |
| Anthropic Claude | "In one line, who trained you?" | "Anthropic" |
| Google Gemini | "In one line, who trained you?" | "Google" |
| Local Ollama | "What is your exact model name and parameter count?" | real model card text |

If the answer names a different org, the test fell through. Do not trust the response.

### 3. Log forensics

Inspect the actual API call in `agent.log` for the model/provider used:

```bash
awk -v since="$(date -d @$(cat /tmp/smoke_baseline_$$) '+%Y-%m-%d %H:%M:%S')" \
  '$0 >= since' ~/.hermes/logs/agent.log \
  | grep -E "conversation turn|API call|Primary provider auth failed"
```

Look for these specific lines and what they tell you:

- `model=<X> provider=<Y>` in a `conversation turn` or `API call` line — the **actual** model that served the request. This is ground truth, regardless of what was requested.
- `WARNING cli: Primary provider auth failed (...): Falling through to fallback: <provider>/<model>` — the trap fired. The response is from the fallback, not the requested model.
- `OpenAI client created ... provider=... base_url=... model=...` — the client config that was actually instantiated. Compare `base_url` to the requested provider's base URL.

If the `base_url` doesn't match the requested provider (e.g. you asked for Nous's `inference-api.nousresearch.com` but the log shows `chatgpt.com/backend-api/codex`), the fallback fired.

## If the trap fires: recovery

```bash
hermes auth add <provider>     # device-code OAuth flow, opens browser
# or, if the provider is API-key-based:
hermes auth add <provider> --api-key
```

Then re-run the smoke test. The `last_status` field on the credential in `~/.hermes/auth.json` should update from `None` to `ok` (or whatever the provider's success indicator is) on a successful refresh.

## Why the trap exists (and why it stays)

Silent fallback is a feature, not a bug — it keeps the user productive when one provider is briefly down. The cost is that successful-looking responses can come from a different model than the user thinks. The verification protocol above is the only reliable way to know which model actually served the request.

For model-alias work, the test belongs in the change set: don't declare an alias "working" until the log forensics confirm the `model=` field matches the alias's `model:` entry. Otherwise the next session will inherit a silently-broken alias and only discover the failure when the cost of a credit-billed fallback shows up.
