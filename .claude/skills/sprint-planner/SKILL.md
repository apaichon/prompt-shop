---
name: sprint-planner
description: Use when planning a new sprint. Reads 06-sprints/_velocity.json and recent retros to propose a realistic commitment.
---

# Sprint Planner

## Steps
1. Run `node scripts/next-id.js sprint`.
2. Read `docs/sdlc/06-sprints/_velocity.json` if it exists. Compute average velocity over the last 3 sprints.
3. List all tasks with `status: proposed|approved` and no `sprint:`. Ask the user which to commit.
4. Copy `docs/sdlc/_templates/sprint.md` to `docs/sdlc/06-sprints/<ID>.md`. Fill `start`, `end`, `goal`, `committed`.
5. For each committed task, set its frontmatter `sprint: <new-sprint-id>`.
