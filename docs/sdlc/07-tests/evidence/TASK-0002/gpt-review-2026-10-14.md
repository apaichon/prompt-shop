# GPT review of TASK-0002 — 2026-10-14

Reviewed the local uncommitted implementation on feature/TASK-0002-catalog-lookup-and-walkable-route, HEAD a564571 (TASK-0001 foundation). No TASK-0002 PR or feature commit exists. The reviewed code consists of eight untracked internal/catalog Go helpers; internal/routing and task-specific tests are absent. Full draft pre-implementation checklist is checked; whole-design signatures and integration approval remain separate pending gates.

## Verdict: CHANGES_REQUESTED

1. **P1 — package fails to compile (internal/catalog/rank.go:45).** `hit` is declared inside `Rank` at lines 16–19 but used in package-level `worse`. `go test -race ./internal/catalog` fails with `undefined: hit`; all callers/server integration are blocked. Move the type to package scope or keep the comparator in the function, then run compilation and race-enabled tests.
2. **P1 — required API/service implementation is absent (internal/catalog/http.go:17; TASK-0002 implementation plan).** The file contains only error serialization. There is no PostgreSQL repository/coherent snapshot, published-only query service, public search/map handlers, constructor/registration handoff or routing package. The three customer endpoints cannot be supplied by this task. Implement the database-backed services/handlers, weighted walkable routing and documented failure cases, then hand registrations to the shared server owner. Shared cmd/server wiring remains TASK-0001 ownership.
3. **P2 — reverse-prefix matching ignores unsupported suffixes (internal/catalog/rank.go:102).** `strings.HasPrefix(query, name+" ")` accepts an entire known alias followed by arbitrary extra content. With a stored milk alias, `milk moon cheese` and `whole milk dragon eggs` return the milk product; unknown words should not establish an item match. Keep prefix matching in the query-to-stored-name direction and require all relevant query tokens for the fallback, or document/test an explicit extraction policy. Add unknown/adversarial suffix cases.
4. **P1 acceptance gap — TEST-0007 has no executable evidence.** No catalog/routing *_test.go files exist. After fixes, provide frozen 30-query top-three results (at least 27 correct), all 60 destination/geometry checks, inactive/unknown IDs, disconnected destination, DB errors, committed import visibility and version-coherent snapshots. Do not mark the task complete from helper-level checks.

## Actual commands/results

- `rtk proxy go test -race ./internal/catalog`: FAIL, `internal/catalog/rank.go:45:17: undefined: hit`.
- `rtk proxy go test -race ./internal/catalog ./internal/routing`: FAIL, same compile error plus routing directory missing.
- Temporary-copy diagnostic: moved only the local `hit` type to package scope to unblock the isolated Rank call. Production files were unchanged. `moon cheese` returned []; `milk moon cheese` and `whole milk dragon eggs` returned milk-whole-1l. This diagnostic reproduces the defect; its successful command exit is not product-test acceptance.
- SHA-256 of all eight catalog files checked again before recording: unchanged during review.

No source fix, commit, push, PR review message or merge was performed. Ledger changes record the review and failed precheck only. The Grok builder retains implementation ownership.
