# TASK-0009 local verification — 2026-10-14

Branch: feature/TASK-0009-backoffice. Dependencies locally incorporated: TASK-0001 a564571 and TASK-0004 edc8da9; neither PR was merged into develop. Environment: macOS, Go 1.26.9, Node 22.17.0, Playwright 1.64.0/Chromium, actual PostgreSQL 16 pinned image. No source Monti credentials or deployment resources were used.

| Executed command | Result |
|---|---|
| Go test -race ./... | Pass; DB integration is explicitly skipped without its separate variable |
| BACKOFFICE_TEST_DATABASE_URL + go test -race -count=1 -v ./internal/backoffice ./internal/config ./internal/platform/httpserver | 4 backoffice tests, 2 config tests, 3 HTTP tests passed; unrelated foundation DB readiness test skipped because TEST_DATABASE_URL was unset |
| Go vet ./... | Pass |
| govulncheck v1.9.0 ./... and verbose scan | No reachable or imported-package vulnerabilities; module-only GO-2026-5932 applies to unused OpenPGP in x/crypto, with no fixed version |
| npm run check | 0 errors, 0 warnings |
| npm test | 28 passed |
| npm run build | Static build succeeds |
| npm run test:browser | 9 customer regression tests passed (7.8s) |
| BACKOFFICE_TEST_DATABASE_URL + npm run test:backoffice | 5 real HTTPS/Go/PostgreSQL tests passed (1.2m) |

Commands are fully specified in internal/backoffice/README.md. The PostgreSQL gate covers actual restricted-role reads/writes, optimistic concurrent conflicts, rollback, alias replacement, draft/publish/archive and catalog audit, bound cursors, publication connectivity, server sessions/revocation and database failure. The race SQL fixture seeds its initial session explicitly; real bcrypt cost-12 login, cookie flags and CSRF denial are exercised through HTTPS in Chromium. Session lifetime/rotation/all protected-route denial matrices use controlled-clock repository fixtures; actual PostgreSQL session validation and logout are also exercised.

The HTTPS fixture serves the actual static portal and actual backoffice handlers with no intercepted admin requests. Its ephemeral certificate is trusted only by the local Playwright context. Credentials are synthetic test-only; traces/failure screenshots are disabled to avoid persisting request bodies/cookie values. Explicit screenshots show catalog/editor fields only. Viewports 320/768/1280px passed keyboard focus, no horizontal overflow and zero axe violations; desktop/mobile screenshots were visually inspected.

Initial failures were corrected: Svelte pattern typing, test input types, test request Host, expired-session CSRF cleanup and explicit logout clearing. A MIME parsing compile error introduced during review was fixed before the final checks. Docker init failed because its disk was full; no other project's data was pruned. Task-owned tmpfs PostgreSQL was used. SQL records/session persisted across fresh repository/app instances over that running database; tmpfs is not evidence of database-container durability.

## Remaining acceptance

- Actual shopper search/route and Live public reads after publish/archive require TASK-0002 integration; this run verifies the same stored records and published-only SQL predicate, not the absent public endpoints.
- Manual screen-reader review, Cloud Run revision/restart and durable database-container persistence remain unexecuted. Candidate is not deployed.
- Accepted dependency/design baseline, separate review approval and high-risk human approval remain merge gates.

TEST-0005 remains blocked; passing local automated commands do not mark full release acceptance or TASK-0009 done.


Final hardening follow-up: rollback cleanup has a 250ms bound. The real SQL store-lock stall test verifies request failure within 1.5s and eventual pool release within 750ms (pgx destroys cancelled connections asynchronously). A first immediate-release assertion was too early; the bounded eventual check was used and the real PostgreSQL test passed three consecutive runs. The real HTTPS CRUD/cookie/CSRF/logout browser case was rerun after this cleanup change and passed (17.8s command total). No fixture-password or CSRF-test literal appears in web/build.

The task-owned temporary PostgreSQL container was stopped after verification; it can be started again for a fresh local fixture. Source tree content was unchanged by final branch sync.
