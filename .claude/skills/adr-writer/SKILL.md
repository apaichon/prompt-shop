---
name: adr-writer
description: Use when capturing an architecture decision (ADR-XXXX) that informs a design.
---

# ADR Writer

## Steps
1. Run `node scripts/next-id.js adr`.
2. Copy `docs/sdlc/_templates/adr.md` to `docs/sdlc/04-adrs/<ID>-<slug>.md`.
3. Ask the user: title, context, decision, consequences.
4. Optionally link from a design: append the new ADR ID to the design's `adrs:` list.
5. Print the file path.
