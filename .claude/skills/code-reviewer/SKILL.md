---
name: code-reviewer
description: Use when reviewing a code diff for a task against its linked design and ADRs.
---

# Code Reviewer

## Steps
1. Read the task. Read each design in `designed_by:` and each ADR linked from those designs.
2. Read the diff. If a PR is open, read it via `gh pr diff <PR#>`; otherwise read the worktree diff: `git -C .worktrees/<TASK>/ diff origin/develop...HEAD`.
3. Check: does the diff implement what the design specifies? Are there scope creeps? Are there violations of the ADRs or the design's **Code Style Guide** / **Folder Style** / **System Dependencies**?
4. Check: are there tests in `verified_by:` that are missing or stale? Flag for QA.
5. Check: are the design's **Pre-Implementation Specs** all checked (data + API contracts, error model, etc.)? If not, this is automatically CHANGES_REQUESTED.
6. Write findings as a `## Review` section appended to the task body, headed with one of:
   - `## Review — PASS` (required string; `git-workflow merge` will refuse without it).
   - `## Review — CHANGES_REQUESTED` followed by a bulleted list of required changes.
7. If PASS: post the same summary as a PR comment via `gh pr comment <PR#> --body-file -`.
