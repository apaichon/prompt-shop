# All task source consolidation — 14 October 2026

User instruction: “merge all codes to main i will start to test from initial”. This explicitly authorizes merging all current task source for initial testing despite the previously disclosed qualification blockers. It supersedes normal completed-task merge gates for this source consolidation only. It does not turn failed TEST results, CHANGES_REQUESTED reviews or blocked tasks into acceptance passes. Existing BLOCK_RELEASE and cloud release guards remain intact. No deployment or new release tag is created; v0.1.0 continues to identify the earlier source snapshot.

The integration role uses sync mode and a separate `.worktrees/ALL-SOURCE-20261014` worktree on `chore/integrate-all-task-source`. Task 1/2/3/4/5/6/9 snapshots already on develop/main are retained. The remaining Task 8, 7 and 10 heads were merged locally without conflicts, preserving their feature histories. The combined branch merges through develop, then a release integration branch merges into main using normal merge commits, without force pushing or rewriting published history.

## Additional source heads

- Task 8 / PR #10: `d016ed6f95828ef44545e65593f68c704a04793c` — cloud release/rollback planning, identity/drift and evidence guards, offline fault/rehearsal checks.
- Task 7 / PR #11: `ca744b1f1b53868dca10e66865ae3b36b854aa64` — proposal sources, template assets and rehearsal/submission instructions. Proposal PDF/PPTX files are excluded from Git; local copies remain in the Task 7 worktree.
- Task 10 / PR #12: `d23d38b48be5a35f167ab4e27728b14530df883d` — pinned private Laya CPU service, bounded worker and ADK adapter, frozen evaluation and actual failure reports.

All ten exact task heads are ancestors of the combined source. [Snapshot inventory](sdlc/07-tests/evidence/ALL-SOURCE-20261014/source-snapshots.json) records them. The new tasks' owned code paths are byte-identical to their feature heads. No PDF/PPTX, model weights, credential/env files or local build contexts are tracked or copied by this merge. Existing ignored local assets and task worktrees are retained.

## Combined checks and review

Executed on the combined checkout: Go package/unit checks pass; 42 deployment/release offline tests, 35 QA harness tests, 42 classifier contract/fault tests, nine agent tests and six ADK boundary tests pass (134 Python tests). Portal unit tests pass 28/28; Svelte check has zero errors/warnings and the production static build succeeds. [Observed commands/results](sdlc/07-tests/evidence/ALL-SOURCE-20261014/checks.json) preserve the output and scope. No new disposable database, browser native-voice or deployed acceptance run was requested or claimed.

Separate GPT integration review verifies preserved feature ancestry, absence of conflicts, unchanged owned module bytes, exact frozen corpus/config and reviewed classifier implementation hashes, intact failed model evidence and absence of PDF/PPTX/weights from tracked files. This is **PASS for the requested source consolidation**. It is not a feature/release acceptance verdict. The main README now reflects the combined state and links [initial local testing](INITIAL-TESTING.md), replacing its stale planning-only description. Historical task handoffs/evidence remain attributed to their original source/time.

## Known starting-test limits

- Actual Task 2 public catalog/search/map/routes and shared Go voice/catalog registration remain incomplete. Customer API errors or missing public voice endpoints are expected; the combined source merge does not implement these missing handlers.
- Real Laya frozen evaluation remains 19/40 correct, below 36/40, with 21 low-confidence abstentions counted as misses. The 2 CPU/4 GiB AMD64-on-ARM emulated readiness probe failed; native deployment quota qualification is pending. Frozen inputs/thresholds are unchanged and original/final-source reports are retained.
- Required canonical seed products, actual Gemini native voice/grounding/latency/recovery, full integrated QA and cloud deployment/release acceptance remain outstanding. Task 6's earlier absence report is historical; Task 10 now supplies actual module source and failed inference evidence.
- Task 7 proposal sources are present, but the team leader/submission destination/exact deadline/public repository/final deployed URL/video and measured rehearsal records remain pending. The repository stays private; no external submission was made.

Merging source leaves task and test status metadata unchanged. The user's next activity is initial local testing on main; keys, DB credentials, private model assets and service startup remain explicit local configuration. No automatic cloud release or approval is implied.
