---
name: deploy-runner
description: Use when recording and executing a deployment.
---

# Deploy Runner

## Steps
1. Run `node scripts/next-id.js deployment`.
2. Copy `docs/sdlc/_templates/deployment.md` to `docs/sdlc/08-deployments/<ID>-<slug>.md`.
3. Ask for environment, version (SemVer `vX.Y.Z`), and the task IDs whose merges are bundled in this release.
4. For a planned release: invoke `git-workflow release-start <X.Y.0>` first, stabilize, then `git-workflow release-finish <X.Y.0>` which tags `main`. For a hotfix: `git-workflow hotfix-start` / `hotfix-finish`. Either way, the resulting tag goes into the DEP frontmatter as `git_tag: vX.Y.Z` and `release_branch: release/X.Y.0` (or `hotfix/...`).
5. Run the deploy command. On success, set `status: done`; otherwise leave `in_progress` or set `blocked` with a note.
6. Invoke `task-progress-update <DEP-ID> done` so propagation stamps `deployed_in:` on linked tasks. The graph exporter will then render this deployment in the release lane keyed by `git_tag`.
7. On rollback, do **not** delete the tag or `reset --hard`. Use `git revert` on `main` against the offending merge commit, open an `OPS-XXXX`, and cut a new `vX.Y.Z+1` patch.
