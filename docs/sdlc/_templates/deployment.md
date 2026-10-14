---
id: DEP-XXXX
type: deployment
title: <deployment title>
status: proposed
owner: devops-agent
created: YYYY-MM-DD
updated: YYYY-MM-DD
risk: medium
tags: []
environment: staging
version: ""
git_tag: ""
release_branch: ""
includes_tasks: []
artifacts: []
related: []
---

# Deployment: <title>

## Plan
…

## Rollback
Use `git revert` against the merge commit on `main`; **never** delete the tag or force-push. Cut a new `vX.Y.Z+1` patch and link it via `related:`.
