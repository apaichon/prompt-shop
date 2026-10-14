---
name: sprint-retrospective
description: Use at sprint end to compute velocity, completion rate, risk burn-down, draft a retrospective doc, and update per-role growth notes.
---

# Sprint Retrospective

## Usage
Invoke with a sprint ID (e.g., `sprint-retrospective SPRINT-0003`).

## Steps

1. Read `docs/sdlc/06-sprints/<SPRINT-ID>.md`. Extract `committed`, `start`, `end`, `goal`.
2. For each task ID in `committed`, locate the task file and read its final `status`, `owner`, `updated`, `points` (if any), and any `risk_notes`.
3. Compute the metrics:
   - `velocity` = count of `done` tasks (or sum of `points` if present).
   - `completion_rate` = `done / committed`.
   - `carry_over` = tasks not `done` (capture their IDs for the next sprint planner).
   - `risk_closed` / `risk_opened` = high/critical-risk items closed vs. opened this sprint.
   - `per_role_done` = group `done` tasks by `owner` (e.g., backend-dev-1, backend-dev-2).
4. Append to `docs/sdlc/06-sprints/_velocity.json` (create if missing):
   ```json
   {"sprint": "<SPRINT-ID>", "velocity": <int>, "completion": <float>, "team_size": <int>, "date": "<today>"}
   ```
   The file is a JSON array of these objects.
5. Draft `docs/sdlc/06-sprints/<SPRINT-ID>-retro.md` with this structure:
   ```markdown
   ---
   id: <SPRINT-ID>-RETRO
   type: sprint
   title: Retro — <SPRINT-ID>
   status: done
   owner: sdlc-orchestrator
   created: <today>
   updated: <today>
   related: [<SPRINT-ID>]
   ---

   # Retrospective — <SPRINT-ID>

   ## Metrics
   - velocity: <int>
   - completion: <float>
   - carry-over: <ids…>
   - risk closed/opened: <int>/<int>
   - per-role done: …

   ## What went well
   - …

   ## What didn't
   - …

   ## Action items
   - [ ] …  (each becomes TASK-XXXX with tags: [process-improvement] and sprint: <next-sprint-id>)
   ```
6. Ask the user (interactive) or read from a passed-in JSON (non-interactive) to fill "What went well", "What didn't", and "Action items".
7. For each action item, run `node scripts/next-id.js task` and create a real task file with `tags: [process-improvement]` and `sprint: <next-sprint-id>` (compute next ID as current sprint number + 1).
8. Update `docs/sdlc/10-growth/<role>.md` for each role that had any `done` work this sprint. Append a dated bullet:
   ```
   - YYYY-MM-DD (<SPRINT-ID>): <role>-N shipped <count> done tasks, <risk-closed> high-risk closed. Highlights: <task ids>.
   ```
   Create the file with frontmatter if it doesn't exist:
   ```yaml
   ---
   id: GROWTH-<role>
   type: growth
   title: Growth log — <role>
   owner: sdlc-orchestrator
   created: YYYY-MM-DD
   updated: YYYY-MM-DD
   ---
   ```
9. Print a summary: sprint metrics, files written, files updated.
