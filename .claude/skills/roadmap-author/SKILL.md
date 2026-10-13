---
name: roadmap-author
description: Use when defining a roadmap outcome (ROADMAP-XXXX) for prompt-shop and mapping measurable milestones to requirements.
---

# Roadmap Author

1. Run `node scripts/next-id.js roadmap` to get the next ROADMAP ID.
2. Copy `docs/sdlc/_templates/roadmap.md` to `docs/sdlc/01-roadmap/<ID>-<slug>.md`.
3. Capture the outcome, horizon, baseline, target metrics, why-now evidence, scope boundaries, milestones, risks, and dependencies.
4. Map milestones to existing requirement IDs when available. New requirements should link back through `advances:`.
5. Set `created` and `updated` to today's date and keep `status: proposed` until outcome, metrics, and ownership are reviewable.
6. Print the file path and summarize the outcome and next milestone.
