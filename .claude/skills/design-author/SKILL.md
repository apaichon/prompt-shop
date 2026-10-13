---
name: design-author
description: Use when drafting a new design (DES-XXXX) that satisfies one or more approved requirements.
---

# Design Author

## Steps
1. List `docs/sdlc/02-requirements/*.md` with `status: approved` that have no `designed_by:` link yet. Ask the user which to address.
2. Run `node scripts/next-id.js design`.
3. Copy `docs/sdlc/_templates/design.md` to `docs/sdlc/03-designs/<ID>-<slug>.md`.
4. Ask the user: design title, problem statement, decision, alternatives considered, consequences. Capture any ADRs needed in `adrs:`.
5. Fill frontmatter `implements:` with the selected REQ IDs.
6. For each implemented requirement, append its ID to that requirement's `designed_by:` list using `task-progress-update --link` (or edit manually for now).
7. Print the file path.
