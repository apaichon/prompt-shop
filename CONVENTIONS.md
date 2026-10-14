# SDLC Conventions — prompt-shop

This project uses a typed-markdown SDLC ledger under `docs/sdlc/`. Every artifact is a markdown file with YAML frontmatter that doubles as a queryable dependency graph.

## File layout

- `docs/sdlc/01-roadmap/` — ROADMAP-XXXX (prioritized outcomes and milestones)
- `docs/sdlc/02-requirements/` — REQ-XXXX (what the system must do)
- `docs/sdlc/03-designs/` — DES-XXXX (how we'll do it)
- `docs/sdlc/04-adrs/` — ADR-XXXX (architectural decisions)
- `docs/sdlc/05-tasks/` — TASK-XXXX (executable work)
- `docs/sdlc/06-sprints/` — SPRINT-XXXX and SPRINT-XXXX-retro
- `docs/sdlc/07-tests/` — TEST-XXXX (verification)
- `docs/sdlc/08-deployments/` — DEP-XXXX (rollouts)
- `docs/sdlc/09-operations/` — OPS-XXXX (incidents / ops events)
- `docs/sdlc/10-growth/` — per-role growth notes from retros

This project places executable tasks after ADRs and sprint planning immediately after tasks, so sprint commitments can reference the defined work and its requirement, design, and verification dependencies. The numeric prefixes are stable navigation identifiers, not execution gates; the workflow below remains authoritative. Do not renumber them when adding a new artifact type; add the new type at the next available number or document an intentional migration.

## IDs

IDs are zero-padded counters per type (e.g., `REQ-0001`, `TASK-0042`). Use `node scripts/next-id.js <type>` to get the next free ID.

## Relationship fields

Every artifact may carry these frontmatter list fields:

- `implements:` (task/design → requirement)
- `advances:` (requirement → roadmap outcome)
- `designed_by:` (task/code → design)
- `verified_by:` (task → test)
- `deployed_in:` (task → deployment)
- `blocks:` / `blocked_by:` (task → task)
- `related:` (catch-all)

These define edges in the graph emitted by `scripts/sdlc-graph.js`.

## Coding-assistant assignment

Tasks also carry `implementation_model: GPT`, `review_model: GPT` and `assignment_status: proposed`. These are assignment metadata, not dependency edges or artifact statuses. `owner` remains the SDLC role; the task ID, builder session and exclusive path form the execution claim. A separate GPT review pass checks the diff and evidence, and GPT coordinates integration. Follow [MODEL-ALLOCATION.md](docs/MODEL-ALLOCATION.md); assigning a builder does not approve or start a task. Record the actual model/client version when executing; no exact model version is selected by this plan.

## Status values

`proposed | approved | in_progress | blocked | done | cancelled`

## Risk values

low, medium, high, critical

## Sprint length

1 days.

## Workflow

1. PM-agent defines or selects a roadmap outcome, then drafts a 5W1H requirement → status `approved`.
2. Architect-agent drafts a design → status `approved`. Lock the design's **Pre-Implementation Specs** before opening any task.
3. PM-agent decomposes the approved requirement and design into 5W1H tasks → assigns to dev role(s) by setting `owner:`.
4. Dev-agent claims the task (`task-progress-update <TASK> in_progress`), invokes `git-workflow start <TASK>`, implements, runs `code-reviewer`, opens a PR via `git-workflow open-pr`, then merges via `git-workflow merge`.
5. QA-agent runs tests; if any fail, the linked task is reverted to `blocked` and `git-workflow resync` is triggered for any dependent open branches.
6. DevOps-agent cuts releases (`git-workflow release-start` / `release-finish`), tags `main`, and runs `deploy-runner` so linked tasks get `deployed_in:` stamped with the `git_tag`.
7. At sprint end, sdlc-orchestrator runs `sprint-retrospective`.

## Git workflow

GitFlow branches (`main`, `develop`, `feature/*`, `release/*`, `hotfix/*`) with **one git worktree per task** under `.worktrees/<TASK-ID>/`. PRs go through `gh`. Full reference: **`GIT_WORKFLOW.md`**. Runnable steps: **`.claude/skills/git-workflow/SKILL.md`**.

Never edit code in the main checkout. Never commit directly to `main` or `develop`. Never force-push to shared branches.

### Task-level lock

A task is locked to its `owner:` while `status: in_progress`. No other agent may start it. The frontmatter is the lock; git is the artifact; they must always agree (run `node scripts/sdlc-propagate.js` after any status change, or rely on the PostToolUse hook).

## Coordination modes (sync · parallel · resync)

When 2+ agents work the **same goal** (e.g., multiple tasks under one requirement), the sdlc-orchestrator (or PM) declares one mode per goal and records it in the sprint doc:

- **sync** — tasks share contracts; do them one at a time. One worktree active per area.
- **parallel** — tasks touch disjoint surfaces proven by the design's *System Dependencies*; each owner runs their own worktree. Daily `git-workflow sync` rebases onto `develop`.
- **resync** — a parallel branch fell behind, or a contract moved, or QA found drift. Affected tasks → `blocked`; each owner runs `git-workflow resync`; contract conflicts go back to architect-agent.

Sprint doc snippet:

```yaml
coordination:
  goal: REQ-0012
  mode: parallel          # sync | parallel | resync
  tasks: [TASK-0042, TASK-0043]
  resync_trigger: "any merge to develop touching DES-0007"
```

## Versioning & history

- `main` is tagged using **SemVer 2.0** (`vMAJOR.MINOR.PATCH`).
- `vX.Y.0` tags come from merged `release/*`; `vX.Y.Z` (Z>0) tags come from merged `hotfix/*`.
- Each tag round-trips to a `DEP-XXXX` deployment doc whose `git_tag:` field is the same string. The SDLC ledger is the human-readable history; `git log --tags --oneline` is the machine-readable one.
- Never rewrite a tagged commit. Use `git revert` to undo merged changes; the revert is itself a ledger event.

## Graph export

`node scripts/sdlc-graph.js` → `docs/sdlc/_graph.json` and `_graph.mmd`. These are git-ignored. The graph renders a **release lane** by reading `git_tag:` on deployment docs.
