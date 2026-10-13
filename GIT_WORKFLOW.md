# Git Workflow — prompt-shop

This document is the single source of truth for how every agent uses git on prompt-shop. Agents must follow it; the `git-workflow` skill executes it. If anything here conflicts with another doc, **this file wins**.

> Companion doc: `CONVENTIONS.md` (SDLC ledger). Companion skill: `.claude/skills/git-workflow/SKILL.md` (the runnable steps).

## TL;DR

- One **git worktree per task**, rooted at `.worktrees/<TASK-ID>/`. Never edit code in the main checkout.
- Branch model: **GitFlow** (`main`, `develop`, `feature/*`, `release/*`, `hotfix/*`).
- One **PR per task**, opened with `gh pr create`, merged with `gh pr merge --squash`.
- A task's `owner:` + `status: in_progress` is its **lock**. No other agent may start it.
- Cross-agent coordination has three modes: **sync**, **parallel**, **resync**. Pick one explicitly per goal.
- Code version history is tracked via **SemVer tags on `main`** plus the SDLC ledger; never rewrite published history.

## 1. Branch model (GitFlow)

| Branch | Purpose | Source | Target | Who opens |
|---|---|---|---|---|
| `main` | Production. Always deployable. Tagged for releases. | — | — | (protected) |
| `develop` | Integration. All feature work converges here. | `main` | `main` (via release/*) | (protected) |
| `feature/<TASK-ID>-<slug>` | One task's work. | `develop` | `devel​op` | dev-agent |
| `release/<X.Y.0>` | Stabilize a release. Bug fixes only. | `develop` | `main` + back-merge to `develop` | devops-agent |
| `hotfix/<X.Y.Z>-<slug>` | Emergency fix to prod. | `main` | `main` + back-merge to `develop` | devops-agent (with dev) |

Rules:
- **Never** commit directly to `main` or `develop`.
- **Never** force-push to `main`, `develop`, or any merged `release/*` / `hotfix/*`.
- `feature/*` branches may be force-pushed by their owner during review (only).
- Delete `feature/*` after merge; keep `release/*` and `hotfix/*` for audit.

Naming examples:
- `feature/TASK-0042-add-voice-intent-router`
- `release/1.4.0`
- `hotfix/1.3.2-nats-reconnect`

## 2. Worktree-per-task

Every task gets its own working copy under `.worktrees/`. This isolates each agent's edits so two agents can work in parallel on the same repo without colliding.

```
<repo-root>/                ← main worktree, branch: develop (read-only for agents)
└── .worktrees/
    ├── TASK-0042/          ← branch: feature/TASK-0042-…
    ├── TASK-0043/          ← branch: feature/TASK-0043-…
    └── REL-1.4.0/          ← branch: release/1.4.0  (optional)
```

Create a worktree (agent never runs raw git — invoke `git-workflow start <TASK-ID>`):

```bash
git fetch origin
git worktree add -b feature/TASK-0042-add-voice-intent-router \
  .worktrees/TASK-0042 origin/develop
```

Remove when the PR is merged:
```bash
git worktree remove .worktrees/TASK-0042
git branch -d feature/TASK-0042-add-voice-intent-router  # local
```

`.worktrees/` is git-ignored; the directory is local-only state.

## 3. Task-level locking

A task is "locked" to its owner when:

```yaml
# docs/sdlc/05-tasks/TASK-0042.md frontmatter
owner: backend-dev
status: in_progress
```

Before any agent starts a task:

1. Read the task file.
2. If `status` is `in_progress` and `owner` is not you → **stop**. The task is locked.
3. If `status` is `proposed` or `approved` and unowned → set `owner: <you>`, then `task-progress-update <TASK-ID> in_progress`. This atomic flip is your lock.
4. The propagation hook (or manual `node scripts/sdlc-propagate.js`) makes the lock visible to other agents.

Releasing the lock = the task reaches `done`, `blocked`, or `cancelled`.

If you genuinely need to **take over** a locked task (original owner stalled), open an `OPS-XXXX` entry stating why, reassign `owner:`, and notify in the sprint doc.

## 4. The per-task lifecycle

```
┌────────────────────────────────────────────────────────────────────┐
│  1. claim task        →  set owner + in_progress                   │
│  2. git-workflow start <TASK-ID>                                   │
│       → fetch, create worktree, branch off origin/develop          │
│  3. implement (task-implementer skill)                             │
│  4. code-reviewer skill                                            │
│  5. git-workflow commit <TASK-ID> "<type>(<scope>): <subject>"     │
│       → uses commit-template.txt with SDLC refs filled in          │
│  6. git-workflow sync <TASK-ID>                                    │
│       → rebase onto latest origin/develop                          │
│  7. git-workflow open-pr <TASK-ID>                                 │
│       → gh pr create --base develop, links REQ/DES/TASK            │
│  8. qa-agent runs tests against the PR branch                      │
│  9. git-workflow merge <TASK-ID>                                   │
│       → gh pr merge --squash --delete-branch                       │
│ 10. git-workflow cleanup <TASK-ID>                                 │
│       → remove worktree, prune local branch                        │
│ 11. task-progress-update <TASK-ID> done                            │
└────────────────────────────────────────────────────────────────────┘
```

Step 5 commit message template (from `commit-template.txt`):

```
<type>(<scope>): <subject>

Body — what changed and why.

SDLC refs:
Requirement: REQ-XXXX
Design:      DES-XXXX
Task:        TASK-XXXX
Test:        TEST-XXXX
```

PR body template (the skill fills these from frontmatter):

```markdown
## Summary
<one paragraph from TASK title + design Decision>

## SDLC refs
- Requirement: REQ-XXXX
- Design:      DES-XXXX
- Task:        TASK-XXXX
- Tests:       TEST-XXXX, TEST-YYYY

## Risk
<risk + risk_notes from the task>

## Test plan
- [ ] <verified_by tests pass locally>
- [ ] <manual check the design's acceptance criteria>
```

## 5. Sync · Parallel · Resync (coordination modes)

When multiple agents work toward the **same goal** (e.g., several tasks under one requirement), the orchestrator picks one mode and writes it into the sprint doc:

### Sync (sequential)
- Tasks share a file area or a tight contract (e.g., schema + API + UI).
- One task at a time per area. Each completes (merged to `develop`) before the next starts.
- Worktrees: one at a time. Branches: short-lived.
- Use when changes are tightly coupled and merges would conflict.

### Parallel (concurrent)
- Tasks touch disjoint areas (e.g., backend handler vs. frontend page vs. infra).
- All agents work simultaneously, each in their own worktree.
- Daily `git-workflow sync <TASK-ID>` rebases each onto the latest `develop`.
- Use when the design's **System Dependencies** block proves the surfaces are disjoint.
- Risk: hidden contract drift. Mitigated by the **Pre-Implementation Specs** lock in the design.

### Resync (recovery)
- Triggered when:
  - A parallel branch falls > 24h behind `develop`, or
  - A merged task changes a contract a parallel branch depends on, or
  - QA finds a contract mismatch between two open PRs.
- Steps:
  1. orchestrator pauses affected tasks (status → `blocked`).
  2. Each owner runs `git-workflow resync <TASK-ID>` — rebases on `develop`, re-runs tests, re-requests review.
  3. Conflicts that touch the design's contracts go back to architect-agent — never papered over in the PR.
  4. orchestrator unblocks tasks one at a time, sync-mode for the remainder.

### Picking a mode

```text
            ┌────────────────────────┐
            │ Tasks share contracts? │
            └─────────┬──────────────┘
              yes     │      no
        ┌────────────┘    └──────────────┐
        ▼                                 ▼
     SYNC                            PARALLEL
        │                                 │
        │  ←─── conflict / drift ───→     │
        └─────────────┬───────────────────┘
                      ▼
                   RESYNC
```

The selected mode is recorded in the sprint doc as:

```yaml
coordination:
  goal: REQ-0012
  mode: parallel        # sync | parallel | resync
  tasks: [TASK-0042, TASK-0043, TASK-0044]
  resync_trigger: "any merge to develop affecting docs/sdlc/03-designs/DES-0007"
```

## 6. PR rules

- **Base branch**: always `develop` for `feature/*`, always `main` for `release/*` and `hotfix/*`.
- **Title**: `<type>(<scope>): <subject>` — same as the squash commit.
- **Body**: PR-body template above. The `git-workflow open-pr` skill fills it from frontmatter.
- **Required checks before merge**:
  - CI green.
  - `code-reviewer` skill has appended a `## Review — PASS` block to the task.
  - All `verified_by:` tests linked in the task are `status: passed`.
  - For `risk: high|critical`, a second human approver is required.
- **Merge strategy**: `--squash` for `feature/*`, `--merge` (no fast-forward) for `release/*` and `hotfix/*` so the merge commit is auditable.
- **After merge**: delete the remote branch (`gh pr merge` does this with `--delete-branch`); `git-workflow cleanup` removes the local worktree.

## 7. Releases & version history (SemVer)

`main` is tagged for every release using **SemVer 2.0**: `vMAJOR.MINOR.PATCH`.

| Tag | Source branch | When |
|---|---|---|
| `vX.Y.0` | `release/X.Y.0` merged to `main` | End of sprint (planned) |
| `vX.Y.Z` (Z>0) | `hotfix/X.Y.Z-*` merged to `main` | Unplanned production fix |

Release procedure (devops-agent):

1. `git-workflow release-start <X.Y.0>` — branches `release/X.Y.0` off `develop`.
2. Stabilize: only bug-fix commits accepted on `release/X.Y.0`.
3. `git-workflow release-finish <X.Y.0>` — merges into `main`, tags `vX.Y.0`, back-merges into `develop`, pushes tag.
4. `deploy-runner` skill records a `DEP-XXXX` entry referencing the tag.
5. The SDLC ledger keeps the human-readable history; `git log --tags --oneline` keeps the machine-readable one.

Hotfix procedure mirrors release but branches off `main` and bumps `PATCH`.

### Code-version ↔ ledger mapping

Each release tag must round-trip to a `DEP-XXXX` entry:

```yaml
# docs/sdlc/08-deployments/DEP-0007.md
id: DEP-0007
type: deployment
status: done
version: v1.4.0
git_tag: v1.4.0
release_branch: release/1.4.0
includes_tasks: [TASK-0042, TASK-0043, TASK-0044]
```

`sdlc-graph.js` reads `git_tag` and renders a release lane in the dependency graph.

## 8. History hygiene

- **Never** `git push --force` to `main`, `develop`, `release/*`, `hotfix/*`, or any branch with an open PR that has reviews.
- **Never** rewrite a tagged commit.
- **Always** preserve PR/commit messages that reference SDLC IDs — they are the audit trail.
- Use `git revert` (not `git reset --hard` then push) to undo a merged change. The revert commit creates a new ledger entry; `task-progress-update` should flip the affected task to `blocked` and link the revert.

## 9. Agent permissions cheat-sheet

| Action | dev | qa | devops | orchestrator | pm | architect | docs |
|---|---|---|---|---|---|---|---|
| Create worktree / feature branch | ✅ own task | — | — | — | — | — | — |
| Open PR (feature) | ✅ | — | — | — | — | — | — |
| Approve PR | (peer dev) | ✅ | ✅ | ✅ | — | ✅ | — |
| Merge PR (feature → develop) | ✅ own | ✅ | ✅ | — | — | — | — |
| Open `release/*` / merge to `main` | — | — | ✅ | — | — | — | — |
| Create release tag | — | — | ✅ | — | — | — | — |
| Force-push (feature only) | ✅ own | — | — | — | — | — | — |
| Revert a merged change | ✅ own | — | ✅ | ✅ | — | — | — |
| Edit ledger after merge | ✅ own task | ✅ tests | ✅ deps | ✅ retros | ✅ reqs | ✅ designs | ✅ docs |

## 10. Cheat-sheet — what to invoke

| Situation | Invoke |
|---|---|
| Start a task | `git-workflow start <TASK-ID>` |
| Pause for the day | (none — keep worktree, commit WIP locally) |
| Daily catch-up | `git-workflow sync <TASK-ID>` |
| Ready to merge | `git-workflow open-pr <TASK-ID>` → review → `git-workflow merge <TASK-ID>` |
| Done | `git-workflow cleanup <TASK-ID>` → `task-progress-update <TASK-ID> done` |
| Conflict / contract drift | `git-workflow resync <TASK-ID>` and notify orchestrator |
| Cut a release | `git-workflow release-start <X.Y.0>` … `release-finish <X.Y.0>` |
| Emergency prod fix | `git-workflow hotfix-start <X.Y.Z>-<slug>` … `hotfix-finish <X.Y.Z>` |

If you need to do something not on this list, **stop and ask the orchestrator** — do not improvise on git history.
