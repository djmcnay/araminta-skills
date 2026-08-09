---
name: research
description: Multi-agent research pipeline for product evaluation, academic literature review, and general web research. Spawns parallel subagents for data collection, runs analysis and hallucination verification, delivers structured reports.
ownership: collab
category: research
---

# Research Skill

## Overview

A general-purpose research pipeline that takes a brief, spawns parallel subagents for web scraping, runs a smart analysis pass, verifies claims against sources, and delivers a structured report.

Designed to expand — start with product research, add academic and general research over time.

## Model Hierarchy

| Role | Model | Provider | Notes |
|------|-------|----------|-------|
| **Scraping agents** | `cheap fast model` or `cheap fast model` | Google free API | Cheap, fast, thorough. Never OpenRouter. |
| **Analysis pass** | `analytical model` | — | Deep reasoning over collected data |
| **Orchestration & report** | `orchestration model` (me) | — | Pipeline control, report polish, personality |

### Scraping Agent Availability

Before spawning scraping subagents, check model availability:
1. Try `cheap fast model` first (cheapest)
2. If unavailable, try `cheap fast model` via Google free API
3. If neither available, surface to the user:

> ⚠️ Primary scraping agents unavailable (`cheap fast model` / `cheap fast model` via Google). How would you like to proceed?

Never silently fall back to an expensive model without asking.

## Pipeline

### 1. Brief Intake

Parse the user's request to determine:
- **Research type:** `product` | `academic` | `general`
- **Subject:** what's being researched (product name, topic, question)
- **Context:** what decision does this support? (buying, building, understanding)
- **Vault target:** where the report should land (optional)

If no research type is specified, infer from context. Default to `product` for tangible things.

### 2. Setup Project Directory

```
research/<type>/<project-slug>/
├── raw/                            # scraped data from subagents
│   ├── _01-formal-reviews-brief.md     ← my instruction to agent
│   ├── formal-reviews.md               ← agent output
│   ├── _02-informal-sentiment-brief.md
│   ├── informal-sentiment.md
│   ├── _03-brand-landscape-brief.md
│   ├── brand-landscape.md
│   ├── _04-alternatives-brief.md
│   └── alternative-implementations.md
├── analysis.md                     # smart analysis pass output
├── verification.md                 # hallucination check results
├── report.md                       # final report
└── operations.md                   # subagent operations summary
```

**Vault fallback logic:**
1. If the user specifies a vault path → use it
2. If a configured vault has a `research/` directory → use it
3. Otherwise → save to `research/tmp/<project-slug>/` and flag:

> ⚠️ Saving to temp location (`research/tmp/`) — move to a proper vault when you have one set up.

Update `research/tmp/.gitignore` if not present:
```
# Temp research outputs — do not commit
*
!.gitignore
```

### 3. Spawn Parallel Subagents

Use `subagent dispatch` in batch mode (up to 3-4 concurrent). Each subagent gets:
- A focused research mandate
- A list of sources to check
- Output format specification
- Scraping agent model (`cheap fast model` or `cheap fast model`)

**Before spawning:** write each subagent's exact instruction to `_NN-<agent>-brief.md` in the raw/ folder. This creates an audit trail of what was asked vs what came back.

#### Product Research — Four Agents

**Agent 1: Formal Reviews**
- Sources: Which?, Trusted Reviews, Wirecutter, specialist blogs, expert roundups, Trustpilot, professional review sites
- Search queries: `"<product>" review 2026`, `"<product>" expert review`, `"<product>" Which review`, `"<product>" Trusted Reviews`
- Output: headline findings, pros/cons from credible sources, star ratings, notable quotes
- Include source URLs for every claim

**Agent 2: Informal Sentiment**
- Sources: Reddit, Amazon reviews, forums, social media (Twitter/X, Facebook groups, TikTok mentions), app store reviews
- Search queries: `"<product>" reddit`, `"<product>" review site:reddit.com`, `"<product>" problems`, `"<product>" long term user experience`
- Output: common praise themes, common complaints, surprising findings, sentiment distribution
- Include source URLs and quote snippets

**Agent 3: Brand Landscape**
- Sources: manufacturer sites, brand heritage pages, press releases, brand comparison articles, industry reputation pieces
- Search queries: `"<brand>" reputation`, `"<brand>" product range`, `"<category>" best brands 2026`, `"<brand>" vs <brand>`
- Output: who makes it, brand reputation, what else they make, how they're positioned in the market
- Include source URLs. Focus on respected names even if not the exact product.

**Agent 4: Challenge & Expand**
This agent's job is not to find alternatives to the product — it's to challenge the brief itself:
- Question the assumptions the user has made (does he actually need feature X?)
- Stretch the category (is a tamper even the right tool? what about a distributor-only workflow?)
- Explore adjacent approaches (palm vs traditional, click vs feel, steel vs brass)
- Find the "I hadn't thought of that" options — things the user didn't ask for but might prefer
- Sources: barista philosophy articles, "unpopular opinion" threads, ergonomic studies, traditional craft makers, Italian/artisan alternatives
- Search queries: `"self leveling tamper unnecessary"`, `"traditional vs calibrated tamper"`, `"palm tamper ergonomics"`, `"espresso tamper unpopular opinion"`, `"Italian brass tamper"`, `"Reg Barber tamper"`, `"Espro tamper"`
- Output: what the user assumed, why it might be wrong, what he should consider instead
- Include source URLs

#### Civic / parliamentary lookups

Use this for UK questions about MPs, constituencies, boundary changes, and voting records.

- Start with the exact postcode or locality name, not the county or a nearby town.
- Prefer search snippets from UK Parliament when they return a direct seat + MP result.
- Use a geographic locator such as Find That Postcode when you need a locality-to-constituency mapping and the Parliament site is hard to extract.
- When the seat may have changed recently, check for boundary review effects and mention if the seat is new, renamed, or cross-county.
- For voting-record questions, the most useful summary is usually the MP’s party-alignment percentage plus the policy-area headings.
- A failed page fetch is not evidence of missing data; retry via search snippets or a second source.

Reference notes: `references/parliamentary-lookup.md`

#### Academic Research — Agents (future)

TBD — will involve arXiv, Google Scholar, Semantic Scholar, citation tracking.

#### General Research — Agents (future)

TBD — flexible agent configuration based on brief.

### 4. Raw Output Format

Each subagent writes to its assigned file in `<project>/raw/`. Format:

```markdown
# [Agent Name] — <project-slug>
_Generated: YYYY-MM-DD HH:MM_

## Sources Consulted
| Source | URL | Date Accessed |
|--------|-----|---------------|
| TechRadar | https://... | 2026-04-17 |

## Key Findings

### [Finding 1]
- **Claim:** specific claim made
- **Source:** which source(s) support this
- **Quote:** direct quote if available
- **Confidence:** high | medium | low

### [Finding 2]
...
```

**Every claim must have a source URL.** No sources = discard the claim.

### 5. Analysis Pass

After all subagents complete, read all raw files and produce `analysis.md`:

1. **Cross-reference:** which claims appear in multiple independent sources?
2. **Contradictions:** where do sources disagree?
3. **Gaps:** what's missing? (no long-term reviews, no comparison with X, etc.)
4. **Weighting:** formal reviews vs user sentiment — do they align?
5. **Synthesis:** what actually matters for the user's decision?

This pass is done by `analytical model` (analytical model), orchestrated by `orchestration model`.

### 6. Hallucination Verification

**Before generating the final report**, run an external check:

1. **Source existence:** open every source URL from the raw files. Confirm it loads and contains the claimed content.
2. **Quote verification:** if a direct quote was extracted, confirm it appears on the source page.
3. **Claim traceability:** for every claim in the analysis, trace it back to at least one verified source.
4. **Staleness:** note any sources older than 12 months for current product generation.

**Unverifiable claims are removed, not flagged.** If a claim cannot be traced to a verified source, it does not appear in the report. No exceptions, no hedging, no `[UNVERIFIED]` labels.

Write results to `verification.md`:
```markdown
# Verification Report — <project-slug>
_Checked: YYYY-MM-DD HH:MM_

## Summary
- Total claims checked: N
- Verified and retained: N
- Removed (no source): N
- Removed (dead link): N
- Removed (quote not found): N

## Removed Claims
### [Claim]
- **Reason:** source URL returned 404 / no source traceable / quote not on page
```

### 7. Iterative Subagent Passes (1-2 allowed)

If during steps 4-6 the analysis reveals:
- A critical gap (missing key comparison, no long-term reviews)
- A hallucination or dead link that breaks a key finding
- A follow-up question that would materially improve the report

Then spawn 1-2 additional focused subagents to resolve. These are short, targeted missions:
- "Find long-term reviews of X (6+ months ownership)"
- "Verify this claim: [specific claim] — find a working source"
- "What is [alternative product Y] and how does it compare?"

Maximum 2 passes. If the gaps persist, note them honestly in the report rather than endlessly scraping.

### 8. Report Generation

Using the template for the research type, generate the final `report.md`. Orchestration by `orchestration model` — the report should have personality and voice, not read like a Wikipedia entry.

#### Product Report Template

```markdown
# Research Report: <Product/Category>
_Requested: YYYY-MM-DD | Completed: YYYY-MM-DD_

## TL;DR
One paragraph. What is it, should the user care, what's the bottom line.

## Key Findings
1. **Finding one** — Source URL
2. **Finding two** — Source URL
3. **Finding three** — Source URL

## Detailed Analysis

### What It Is
Brief description of the product/category.

### Strengths
- Point one — Source URL
- Point two — Source URL

### Weaknesses & Risks
- Point one — Source URL
- Point two — Source URL

### What Users Actually Say
Synthesis of user sentiment — common praise, common complaints, surprises.

### The Brand
Who makes it, reputation, positioning in market.

### Alternatives & Options
Things the user might not have considered:
- **Alternative A** — how it compares — Source URL
- **Alternative B** — how it compares — Source URL

## My Assessment
Honest opinion. Not hedged. What would I do. **Challenge the user's assumptions here** — if his brief said "must have X" but the research suggests X isn't necessary or Y is better, say so. The report should stretch his thinking, not just confirm what he already believed.

## Sources
| # | Source | URL |
|---|--------|-----|
| 1 | TechRadar | https://... |

## Verification Notes
- N claims verified, N removed (no source / dead link / quote not found)
```

### 9. Delivery — Three Parts

the user receives three things:

#### Part 1: Minty's Summary
A short, casual, voice-note-style summary. The kind of thing I'd say if I had a voice:
- What I found (the headline)
- What surprised me
- What I'd do if I were you
- Any flags

Written in first person, warm but honest. Not a regurgitation of the report — just my take.

#### Part 2: The Report
The full structured report (`report.md`). Saved to vault/tmp, summary sent in chat with bare URL to full version.

#### Part 3: Operations Summary
Brief account of what happened behind the scenes in `operations.md`:
- Which subagents were spawned and what they were asked
- How each performed (thorough, thin, had issues)
- Any hallucinations caught and removed
- Any iterative passes and why
- Any model availability issues

Format:
```markdown
# Operations Log — <project-slug>

## Subagent Performance
| Agent | Model | Sources Found | Issues | Passes |
|-------|-------|---------------|--------|--------|
| Formal Reviews | cheap fast model | 12 | none | 1 |
| Informal Sentiment | cheap fast model | 8 | 2 hallucinations removed | 1 |
| Brand Landscape | cheap fast model | 6 | thin — sent back for more | 2 |
| Alternatives | cheap fast model | 10 | none | 1 |

## Issues & Resolves
- [Issue description and how it was handled]

## Model Availability
- All primary agents available / [any issues]
```

---

## Hardware Compatibility Checks (Lightweight Inline)

For quick compatibility checks when the user is ordering 2-4 components from the same vendor — typically retailer accessories (HATs, displays, microphone arrays, speakers, NVMe Base). This is a *lightweight inline review* done directly by reading product pages, not the full multi-agent pipeline.

**Use case signals:** the user sends multiple product URLs and asks if they'll work together, or asks "what cables am I missing," or asks to find a better-suited alternative for a specific part in a multi-component build.

### Quick-check checklist (do these yourself, not via subagents)

1. **Extract interface & connector from each product page** — HDMI vs GPIO/SPI vs USB vs I2S, connector types (JST PH 2.0mm, micro-HDMI, USB-C, 3.5mm), power requirements
2. **Cross-reference physical stacking** — does the NVMe Base pass GPIO through for HATs? Does the display use the same HDMI port? Do audio devices need the same USB port?
3. **Check for OEM companion parts** — the ReSpeaker Lite has a Seeed-branded companion speaker that uses the correct JST mate. Always check for first-party companions before recommending generics.
4. **Identify missing cables** — micro-HDMI to HDMI (common omission), USB-A to USB-C (for ReSpeaker + display touch). List them as a simple shopping list.
5. **Power budget** — host machine 5 (up to 3A) + NVMe (~0.5A) + ReSpeaker (~0.1A) + display USB (~0.3A) + HAT (<0.05A) = within 27W/5A PSU, but check peak current for each.

### Output format

Deliver a **compatibility table** like:

| Part | Compatible | Notes |
|------|------------|-------|
| ReSpeaker Lite | ✅ | USB audio device, detects as sound card |
| Speaker X | ⚠️ | Connector uncertain — OEM Seeed speaker preferred |

Then a **recommended BOM** (original items with substitutions) and a **cable shopping list** as bare bullets.

### Reference file

Detailed checklist and pitfall reference: `references/hardware-compatibility-checks.md`

---

## Depth Settings

| Setting | Light | Standard | Deep |
|---------|-------|----------|------|
| Scraping agents | 2 | 4 | 4 + extra passes |
| Sources per agent | 5-8 | 10-15 | 20+ |
| Iterative passes | 0 | 1-2 | 2+ |
| Verification | spot-check | full | full + re-scrape dead links |

Default: **Standard**

## Hard Rules

1. **No claim without a source.** If you can't trace it, it doesn't go in the report.
2. **Unverifiable claims are removed, not flagged.** No `[UNVERIFIED]` labels — if it can't be proven, it doesn't exist.
3. **No purchasing, no account actions.** This is research only.
4. **Flag tmp storage.** Never silently save to temp.
5. **Verification is mandatory.** Don't skip it to save time.
6. **Bare URLs for all links.** No markdown link syntax — breaks on WhatsApp.
7. **Respond in the originating channel.** Never cross channels.
8. **Never silently escalate model costs.** If scraping agents are unavailable, ask the user.
9. **Challenge the brief.** Don't just find what the user asked for — question whether he asked for the right thing. Stretch his thinking like a bendy yoga lady.
