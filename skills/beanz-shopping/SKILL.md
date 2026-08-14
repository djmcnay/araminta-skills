---
name: beanz-shopping
description: Use when browsing or comparing Beanz UK coffee without accessing a personal account. Queries the public Algolia catalogue for 1kg espresso coffee and produces reproducible price comparisons.
ownership: collab
version: 2.0.0
author: Araminta Milland-Wilde + David McNay
license: MIT
metadata:
  hermes:
    tags: [coffee, shopping, beanz, algolia, uk]
    related_skills: [price-spy]
---

# Beanz Shopping

> **Bullets (read me first):**
> - This is the portable, read-only Beanz UK catalogue skill.
> - It has no account credentials, browser session, order history, address, or personal preferences.
> - Use `scripts/beanz-query.py` rather than scraping the product listing page.
> - Account actions, order history, and checkout preparation belong to the private `beanz-buying` skill.

## Overview

Beanz UK exposes its product catalogue through a public, read-only Algolia index. This skill filters and compares that catalogue without a logged-in browser. Its default query is a useful general espresso profile: 1kg, caffeinated, medium or darker roast.

The script reads Beanz's public, read-only Algolia configuration from the live catalogue page each time it runs. It has no local configuration or account data.

## When to use

- Browse current Beanz UK coffee availability.
- Compare prices per kg, roasters, roast levels, tasting notes, or product types.
- Produce a shortlist before a purchase.
- Monitor catalogue or price changes with a separate price-monitoring workflow.

Do not use this skill to inspect an account, retrieve purchase history, add products to a cart, prepare checkout, or place an order. Load `beanz-buying` instead.

## Catalogue query

Run from the skill directory:

```bash
python3 scripts/beanz-query.py
python3 scripts/beanz-query.py --roast dark --max-price 40
python3 scripts/beanz-query.py --json
python3 scripts/beanz-query.py --save --format markdown
```

The output is sorted by price and identifies the query timestamp. `--save` writes a local snapshot for comparison, not a purchase record.

## Configuration discovery

No configuration file is required. `scripts/beanz-query.py` fetches the public Beanz catalogue page with a browser user agent and extracts the read-only search configuration that Beanz itself publishes. If Beanz changes its page structure, rediscover the fields with:

```bash
python3 ../price-spy/scripts/algolia-retail-query.py discover https://www.beanz.com/en-gb/coffee
```

## Common pitfalls

1. Do not browser-scrape the product grid. It is incomplete and client-rendered.
2. Do not put account data, an address, email history, or purchase preferences in this public skill. Portability is not a reason to publish a household profile.
3. A catalogue query does not establish stock or checkout eligibility. Verify those during a private purchasing flow.
4. Do not treat the public Algolia key as permission to write data. It is read-only catalogue access.

## Verification checklist

- [ ] `python3 -m py_compile scripts/beanz-query.py` passes.
- [ ] `python3 scripts/beanz-query.py --max-price 40` returns current coffee rows.
- [ ] No account-specific scripts or personal data exist in this package.
