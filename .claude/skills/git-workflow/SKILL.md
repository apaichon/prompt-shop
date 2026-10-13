---
name: git-workflow
description: Use whenever an agent needs to touch git for a task — worktree create, branch, commit, sync, open/merge PR, cleanup, release, hotfix, or resync. Implements the GitFlow + worktree-per-task model in GIT_WORKFLOW.md.
---

# Git Workflow

Authoritative runbook for every git action on this project. Read `GIT_WORKFLOW.md` once for the rationale; use this skill for the commands.

## Pre-flight (always)

1. Confirm you are inside the repo: `git rev-parse --show-toplevel`.
2. Confirm `origin` is reachable: `git fetch origin --prune`.
3. Confirm the task exists and you own it: read `docs/sdlc/05-tasks/<TASK-ID>.md`; verify `owner: <you>` and `status: in_progress`. If not, **stop** and reclaim via `task-progress-update <TASK-ID> in_progress` first.

## Verbs

### `start <TASK-ID>`
Create the worktree and feature branch for a task.

```bash
TASK=<TASK-ID>
SLUG=$(grep -E '^title:' docs/sdlc/05-tasks/${TASK}.md | sed 's/title: *//' | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-' | cut -c1-40)
BRANCH="feature/${TASK}-${SLUG}"
git fetch origin
git worktree add -b "${BRANCH}" ".worktrees/${TASK}" origin/develop
echo "worktree: .worktrees/${TASK}  branch: ${BRANCH}"
```

If the worktree already exists, switch into it instead of recreating.

### `commit <TASK-ID> "<message>"`
Commit staged changes inside the worktree, with SDLC refs auto-appended from the task frontmatter.

```bash
TASK=<TASK-ID>
cd ".worktrees/${TASK}"
# Resolve linked IDs from the task frontmatter (implements / designed_by / verified_by)
REQ=$(awk '/^implements:/,/^[a-z]+:/' ../../docs/sdlc/05-tasks/${TASK}.md | grep -oE 'REQ-[0-9]+' | head -1)
DES=$(awk '/^designed_by:/,/^[a-z]+:/' ../../docs/sdlc/05-tasks/${TASK}.md | grep -oE 'DES-[0-9]+' | head -1)
TST=$(awk '/^verified_by:/,/^[a-z]+:/' ../../docs/sdlc/05-tasks/${TASK}.md | grep -oE 'TEST-[0-9]+' | head -1)
git commit -m "$1" -m "SDLC refs:
Requirement: ${REQ:-—}
Design:      ${DES:-—}
Task:        ${TASK}
Test:        ${TST:-—}"
```

Multiple commits per task are fine; the squash-merge collapses them.

### `sync <TASK-ID>`
Daily rebase onto the latest `develop`. No-op if already up to date.

```bash
TASK=<TASK-ID>
cd ".worktrees/${TASK}"
git fetch origin
git rebase origin/develop
# If conflicts: stop, do NOT auto-resolve, escalate to orchestrator.
```

### `open-pr <TASK-ID>`
Push the branch and open a PR against `develop`.

```bash
TASK=<TASK-ID>
cd ".worktrees/${TASK}"
git push -u origin HEAD

# Build PR body from task frontmatter
TITLE=$(grep -E '^title:' ../../docs/sdlc/05-tasks/${TASK}.md | sed 's/title: *//')
REQS=$(awk '/^implements:/,/^[a-z]+:/' ../../docs/sdlc/05-tasks/${TASK}.md | grep -oE 'REQ-[0-9]+' | paste -sd, -)
DESS=$(awk '/^designed_by:/,/^[a-z]+:/' ../../docs/sdlc/05-tasks/${TASK}.md | grep -oE 'DES-[0-9]+' | paste -sd, -)
TSTS=$(awk '/^verified_by:/,/^[a-z]+:/' ../../docs/sdlc/05-tasks/${TASK}.md | grep -oE 'TEST-[0-9]+' | paste -sd, -)
RISK=$(grep -E '^risk:' ../../docs/sdlc/05-tasks/${TASK}.md | sed 's/risk: *//')

gh pr create --base develop --title "${TASK}: ${TITLE}" --body "$(cat <<EOF
## Summary
${TITLE}

## SDLC refs
- Requirement: ${REQS:-—}
- Design:      ${DESS:-—}
- Task:        ${TASK}
- Tests:       ${TSTS:-—}

## Risk
${RISK:-medium}

## Test plan
- [ ] All verified_by tests pass locally
- [ ] Acceptance criteria from linked design satisfied
EOF
)"
```

### `merge <TASK-ID>`
Squash-merge the PR after review + CI + tests.

```bash
TASK=<TASK-ID>
cd ".worktrees/${TASK}"
# Pre-conditions you MUST verify before this command:
#   - code-reviewer wrote "## Review — PASS" on the task
#   - every TEST-* in verified_by has status: passed
#   - CI is green on the PR
#   - if risk: high|critical, a second human approver has signed off
gh pr merge --squash --delete-branch
```

### `cleanup <TASK-ID>`
Remove the worktree and local branch after a successful merge.

```bash
TASK=<TASK-ID>
BRANCH=$(git -C ".worktrees/${TASK}" rev-parse --abbrev-ref HEAD)
git worktree remove ".worktrees/${TASK}"
git branch -d "${BRANCH}" 2>/dev/null || true
git fetch origin --prune
```

### `resync <TASK-ID>`
Recover a branch that fell behind or whose contracts moved. Used in the **resync** coordination mode.

```bash
TASK=<TASK-ID>
cd ".worktrees/${TASK}"
git fetch origin
git rebase origin/develop
# If a rebase conflict touches a file owned by another design (check `git diff --name-only`
# against docs/sdlc/03-designs/*.md), STOP and notify architect-agent.
# Otherwise:
#  - re-run the affected tests (test-runner skill)
#  - re-request review (gh pr review --request)
#  - leave a note on the task: "Resynced against develop @ <sha>"
```

### `release-start <X.Y.0>`
Begin a release stabilization branch (devops-agent only).

```bash
VER=<X.Y.0>
git fetch origin
git worktree add -b "release/${VER}" ".worktrees/REL-${VER}" origin/develop
echo "release branch: release/${VER} in .worktrees/REL-${VER}"
```

### `release-finish <X.Y.0>`
Merge a release into `main`, tag it, back-merge to `develop`.

```bash
VER=<X.Y.0>
cd ".worktrees/REL-${VER}"
git push -u origin HEAD

# Open + merge PR to main (no-ff so the merge commit is preserved)
gh pr create --base main --title "release: v${VER}" --body "See DEP-XXXX for contents."
# After review:
gh pr merge --merge --delete-branch=false

# Tag main
git fetch origin
git checkout main && git pull --ff-only origin main
git tag -a "v${VER}" -m "Release v${VER}"
git push origin "v${VER}"

# Back-merge into develop so develop has the release fixes
git checkout develop && git pull --ff-only origin develop
git merge --no-ff "v${VER}" -m "chore: back-merge v${VER} into develop"
git push origin develop

# Then create DEP-XXXX via deploy-runner and stamp git_tag: v${VER}
```

### `hotfix-start <X.Y.Z>-<slug>`
Branch off `main` for an emergency fix.

```bash
NAME=<X.Y.Z>-<slug>
git fetch origin
git worktree add -b "hotfix/${NAME}" ".worktrees/HOTFIX-${NAME}" origin/main
```

### `hotfix-finish <X.Y.Z>`
Mirror of `release-finish` but starts from `main` and bumps PATCH.

## Hard rules (skill must enforce)

- **Refuse** to commit, push, or open a PR from the main worktree (`git rev-parse --show-toplevel` == cwd). Force the agent into `.worktrees/<TASK-ID>/`.
- **Refuse** `--force` / `--force-with-lease` against `main`, `develop`, `release/*`, `hotfix/*`.
- **Refuse** to merge a PR if the task lacks `## Review — PASS` or has a `verified_by:` test with status ≠ `passed`.
- **Refuse** to delete a worktree whose branch has uncommitted changes (run `git status -sb` first).
- On any unexpected git state (detached HEAD, conflicts, unrelated histories, mid-rebase), **stop** and escalate to `sdlc-orchestrator` rather than improvise.

## Coordination handoff

After every state change (`start`, `merge`, `cleanup`, `release-finish`), invoke `task-progress-update` so the SDLC ledger and the dependency graph stay in sync with git reality. The frontmatter is the lock; git is the artifact; they must agree.
