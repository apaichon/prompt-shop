# QA execution — 14 October 2026

Task: TASK-0006. Builder/review assistant: GPT/Codex; accountable role: qa-agent. User confirmed the candidate is **not deployed**. Branches are inventoried in `source-inventory.json`; they are separate local snapshots, not one integrated release. No secrets were read/copied and no other task's production files were edited.

| Gate | Executed evidence | Outcome / owning handoff |
|---|---|---|
| Frozen catalog authority | Verbatim TASK-0001 seed; 30 unchanged expected prompts; 40 balanced intent inputs; SHA-256 validation | 60 published/eight aisles; three required canonical products missing. TASK-0001: add distinct skimmed milk, plain yogurt, canned chickpeas, then QA binds/refreezes and reruns all trials |
| Geometry fixture | Independent polygon/edge oracle and connectivity for all 60 destinations | All stored destinations connected; no fixture edge crosses a shelf interior. This is fixture validation, not returned production routes |
| Public catalog/routes | Real TASK-0009 local Go server + PostgreSQL + built Svelte static portal, HTTPS loopback | 0/30 catalog positives; all return 404. Eight negative/validation probes also fail. Store map 404 means zero returned routes could be verified. TASK-0002 must compile, supply routing, integrate and pass review |
| Anonymous authorization | Twenty direct Go HTTP probes, same local fixture | 20/20 pass: missing/invalid maintainer cookie on eight protected routes, three private paths unavailable, untrusted-origin login rejected. Full deployed/valid-session gate remains blocked |
| Imports | TASK-0001 `go test -race -count=1 ./...` with a task-owned disposable PostgreSQL database | Suite passes, including real idempotency/update/rollback integration. Public visibility of updates remains untested because the public API is unavailable |
| ADK module | TASK-0003 locked/offline Python tests and isolated Go gateway check | Python 9 pass; Go 8 pass, PostgreSQL atomic-ticket case skipped (its env unset). Provider/audio/checkpoint fixtures do not prove live native voice or actual Laya |
| Staging tooling | TASK-0005 standard-library tests | 13 pass offline; no candidate deployed, no cloud acceptance implied |
| Backoffice components | TASK-0009 real PostgreSQL lifecycle and Go auth/config tests; static-host tests; portal unit tests | Go component checks pass and 28 portal unit tests pass. Valid-session auth/CRUD component checks do not establish public shopper consistency, deployed expiry/rotation/persistence or browser accessibility |
| Native voice / Laya | No real native model or pinned checkpoint acceptance run | TASK-0003 + TASK-0010 integration, real checkpoint/license/assets and deployed native model→ADK→Laya→catalog→audio/card/map evidence required |
| Browser latency/recovery/accessibility | No new deployed microphone/browser benchmark | Warm 30-turn audio/card, typed/route, classifier, cold/fault and manual check evidence remain empty; no latency number fabricated |

TASK-0002's source fails its own catalog compile check with `internal/catalog/rank.go:45:17: undefined: hit`; `internal/routing/` is absent. Its uncommitted source hashes are retained, so the commit alone is not presented as the tested implementation. This is a module-owner fix, not a QA code edit.

Execution corrections are not hidden: an initial fixture start failed because the disposable URL was unquoted in zsh, and the initial local collector recorded 30 transport failures. It was a fixture setup attempt, not a warm release benchmark. The corrected server was started before the recorded HTTP run. An initial Go command also named nonexistent `internal/platform/static`; the overall command exited 1 despite backoffice/config passing, then the actual `internal/platform/httpserver` package was tested successfully. No application defect or pass is inferred from these invocation mistakes. All actual release-normal trials must be preserved without rerun replacement.

The local server and task-owned tmpfs PostgreSQL container were stopped after collection. Existing project containers were not modified. Local fixture credentials were synthetic, never used in candidate probes or recorded as evidence.

Recommendation: **BLOCK_RELEASE**. Return module fixes to their named owners, integrate reviewed dependencies, deploy an immutable candidate through TASK-0005, and rerun the frozen full suites with actual model/checkpoint and reviewed browser/auth/data evidence. The feature-freeze decision, high-risk human review and deployment approval are still outstanding. Missing external evidence is not converted into a harness pass.
