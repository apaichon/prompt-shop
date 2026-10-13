---
name: risk-review
description: Use to surface high/critical-risk artifacts that have not been updated recently.
---

# Risk Review

## Steps
1. Walk all `docs/sdlc/**/*.md`. Parse frontmatter.
2. Filter to `risk: high|critical`.
3. Sort by `updated:` ascending. Flag any with `updated:` older than 7 days (or older than the current sprint's start, whichever is greater).
4. Print a console table: ID, type, owner, risk, updated, title.
5. Suggest next actions per item.
