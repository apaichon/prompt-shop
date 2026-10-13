---
name: task-implementer
description: Use when implementing a task (TASK-XXXX). Reads the task and linked design, writes code, runs code-reviewer before marking done.
---

# Task Implementer

## Steps
1. Read the task file in `docs/sdlc/05-tasks/`. Verify its 5W1H execution canvas, graph, workflow, and outcome are complete, then verify `owner: <you>`; if not, claim it via `task-progress-update <TASK> in_progress` (this is your lock). Stop for clarification if the intended deliverable or outcome evidence is ambiguous.
2. Read each design in `designed_by:` (including its **Pre-Implementation Specs** — every box must be checked or stop) and each requirement in `implements:`.
3. Invoke `git-workflow start <TASK>` to create the worktree + feature branch off `develop`. **All file edits happen inside `.worktrees/<TASK>/`.**
4. Follow the task's execution workflow and implementation plan. Implement the code per the design and keep the task workflow current if discoveries change the approach. Follow project conventions in CLAUDE.md / CONVENTIONS.md and the design's **Code Style Guide** / **Folder Style** sections.
5. Run the test suite for the affected area (use `test-runner`).
6. Invoke `code-reviewer` against your diff.
7. If review passes, invoke `git-workflow commit <TASK> "<type>(<scope>): <subject>"`. If it fails, fix and re-review.
8. `git-workflow sync <TASK>` to rebase onto the latest `develop`.
9. `git-workflow open-pr <TASK>` to push and open the PR.
10. After CI green + tests passed + reviewer PASS, `git-workflow merge <TASK>`, then `git-workflow cleanup <TASK>`.
11. Record the observable outcome evidence in the task, then run `task-progress-update <TASK> done`. Propagation stamps `verified_by:`, `deployed_in:`, etc.

If at any step git fails (conflicts, detached HEAD, push rejected), **stop** — invoke `git-workflow resync <TASK>` and escalate to `sdlc-orchestrator`. Never improvise on history.
