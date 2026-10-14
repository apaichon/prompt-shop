# Protected catalog backoffice

TASK-0009 supplies server-enforced maintainer login/session/CSRF, product list/filter/pagination, draft saves and explicit publish/archive on the single demo-store catalog. The Svelte route is `web/src/routes/backoffice/`; it shares TASK-0004's root layout. All API calls use relative same-origin paths. Session/CSRF values and unsaved edits remain in browser memory; explicit logout clears them. Session expiry keeps an unsaved edit for re-login. Conflicts require explicit latest-version reload before another save.

## Runtime setup

The integrated server reads these operator-provided settings:

- `DATABASE_URL`: public read-only login, pool maximum two.
- `BACKOFFICE_DATABASE_URL`: separate LOGIN granted `prompt_shop_backoffice`, pool maximum two; never the operator URL.
- `PUBLIC_ORIGIN`: exact HTTPS portal origin. HTTP is allowed only for localhost/loopback development; cookies remain Secure.
- `ADMIN_PASSWORD_HASH`: bcrypt cost 12, generated from a strong 16–72 UTF-8 byte password. Keep it server-side in Secret Manager; in a shell env file use single quotes around the hash to preserve dollar signs.
- `STATIC_DIR`: built portal root (`web/build` locally, `/app/web/build` in the TASK-0005 image).

Provision the LOGIN via the operator and apply the existing `migrations/roles.sql`; no schema migration was added. Backoffice is disabled unless its DB URL and hash are set together with PUBLIC_ORIGIN. Partial configuration fails startup. A shared PUBLIC_ORIGIN alone can be used by the voice gateway. Missing backoffice configuration returns a safe 503 instead of granting access. The server owns the static filesystem capability with `os.OpenRoot`; API/socket/private routes never receive HTML fallback. Full readiness still requires the ADK/Laya services.

Generate a hash without putting the password in command arguments:

```sh
rtk proxy sh -c 'python3 -c "import getpass; print(getpass.getpass(\"Maintainer password: \"))" | env -u GOROOT /opt/homebrew/bin/go run ./internal/backoffice/cmd/password-hash'
```

The helper prints only the bcrypt hash. Put it in your private env file/Secret Manager, not the repository. Build the portal from web/ with `rtk proxy npm ci` and `rtk proxy npm run build`, then run `rtk proxy env -u GOROOT /opt/homebrew/bin/go run ./cmd/server` with the runtime environment loaded. TLS terminates at the approved ingress in deployment.

## Security and transaction behavior

Tokens are 32 random bytes; only SHA-256 hashes are stored in PostgreSQL. Eight-hour sessions are absolute and never extended on reads. New login revokes the previous cookie's session atomically; logout deletes the row and clears `__Host-maintainer` (Secure, HttpOnly, SameSite=Strict, Path=/, no Domain). Password rotation must revoke all sessions with an operator transaction and retire old revisions; simply changing the hash does not revoke existing sessions.

Every protected read checks the server session. Every write checks session, exact Origin and constant-time CSRF equality; it rechecks/locks the session row within the mutation transaction so a completed logout cannot race a stale write. Product changes use the same store advisory lock as import, check expected_version, replace aliases atomically, increment catalog/product versions and append audit. Saves always become draft. Publish requires an existing reachable mapped shelf and English alias coverage. Archive retains the record. No map editor, bulk upload, hard delete or commerce controls exist.

Inputs reject unknown/duplicate JSON keys, invalid IDs/FKs, missing fields, duplicate normalized aliases, overlong text and >16KiB bodies. Admin list pages have 50 rows; the cursor binds the last ID to query/state. Queries are parameterized and aliases/pages come from coherent read snapshots. DB work has a 750ms budget inside the 1.5s handler budget; rollback cleanup has a separate 250ms bound. Login comparison uses cost 12 and two CPU slots, plus 5/min/IP burst 2 admission; writes use 20/min/session burst 2 with Retry-After. Direct transport IP is used, so forwarded headers cannot bypass limits; TASK-0005 must agree any trusted platform-proxy policy before adjusting it. Across replicas these are per-instance limits, not a global quota.

No request/body/cookie/password/SQL-error logger was added. Maintenance is operator-owned: purge expired session rows daily (login also prunes expired sessions); retain catalog_audit seven days. The backoffice DB role cannot run those audit deletions, map edits, import receipts or DDL.

## Verification

From repository root:

```sh
rtk proxy env -u GOROOT /opt/homebrew/bin/go test -race ./...
rtk proxy env -u GOROOT /opt/homebrew/bin/go vet ./...
rtk proxy env -u GOROOT /opt/homebrew/bin/go run golang.org/x/vuln/cmd/govulncheck@v1.9.0 ./...
```

For real PostgreSQL coverage use a **disposable database named prompt_shop_task9**. `BACKOFFICE_TEST_DATABASE_URL` is operator-only and the integration test drops/recreates its public schema. The fixture server has the same guard plus localhost host checking. Never point these tools at shared, acceptance or deployed data. Unit tests without that variable explicitly skip the database gate.

This run created a task-owned local tmpfs PostgreSQL container because Docker disk was full; other projects were not pruned. Example local fixture container (synthetic test credentials only):

```sh
rtk proxy docker run -d --name prompt-shop-task9-db-memory --tmpfs /var/lib/postgresql/data:rw,size=192m -e POSTGRES_PASSWORD=task9-disposable-only -e POSTGRES_DB=prompt_shop_task9 -p 127.0.0.1:55449:5432 postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea -c shared_buffers=16MB -c max_connections=20
rtk proxy env -u GOROOT BACKOFFICE_TEST_DATABASE_URL=postgres://postgres:task9-disposable-only@127.0.0.1:55449/prompt_shop_task9?sslmode=disable /opt/homebrew/bin/go test -race -count=1 -v ./internal/backoffice
```

If the named task container already exists, use `rtk proxy docker start prompt-shop-task9-db-memory` instead of creating it again. It was stopped after this run; tmpfs data resets on stop and the test commands reinitialize the disposable schema.

From web/:

```sh
rtk proxy npm run check
rtk proxy npm test
rtk proxy npm run build
rtk proxy npm run test:browser
rtk proxy env BACKOFFICE_TEST_DATABASE_URL=postgres://postgres:task9-disposable-only@127.0.0.1:55449/prompt_shop_task9?sslmode=disable npm run test:backoffice
```

Run SQL tests and the browser fixture **sequentially**; both reset the disposable schema. The HTTPS fixture server uses the actual Go handlers, restricted role and PostgreSQL repository, serves the actual static build, and generates an ephemeral self-signed certificate in memory. Only Playwright's local fixture context ignores that certificate. Its test password is synthetic and the fixture command is never built into the production server image. Backoffice traces/screenshots on failure are disabled to avoid persisting login bodies/cookies; explicit authenticated UI screenshots contain no session/CSRF values. Do not enable traces on real credential runs.

Tests cover cookie attributes, anonymous/invalid/expired/logout denial, CSRF/Origin on mutations, strict bodies, rate buckets, SQL draft/publish/archive, stale/concurrent versions, invalid-write rollback, aliases, >50 pagination, unmapped publishing, repository/app restart over the same DB, narrow grants and bounded outage. The database race test seeds a session as a setup fixture; real cost-12 login is exercised by the HTTPS browser test because race instrumentation can exceed the production handler deadline. The initial tmpfs DB has no durable volume: app/repository restart evidence is distinct from database/container persistence across DB replacement.

## Handoff

- TASK-0001/integration: cmd/server/config/static wiring changes are serialized in this branch. Keep schema/grants unchanged. Compose backoffice.Register with catalog and voice registrations when integrating their modules; do not overwrite one with another.
- TASK-0002: this task changes the shared products/aliases/store versions using the same lock as import. Search and direct route/tool reads must continue to require published state and fresh coherent snapshots. SQL checks prove published filtering and retained labels; the actual shopper search/route endpoint gate awaits TASK-0002.
- TASK-0005: existing proposed ADMIN_PASSWORD_HASH, BACKOFFICE_DATABASE_URL, PUBLIC_ORIGIN and STATIC_DIR handoff names now match implemented configuration. Inject hash/DB secret only into Go. Schedule session/audit retention and complete trusted-proxy policy. Test DB-container persistence and deployed revision behavior separately.
- TASK-0006: TEST-0005 contains executed local evidence and remaining integration/manual/deployment gates.

## Reuse

Monti reference `excerpts/backoffice-catalog.ts.txt` informs catalog pagination, editor state and draft transitions. `excerpts/catalog-validation.go.txt` informs trim/length/state validation. New code replaces source tenant/commerce dependencies with our schema, CSRF and version contracts. The source snapshot is unchanged; MIT attribution remains in web/static/MONTI-LICENSE.txt and web/NOTICE.md. See references/monti-jarvis/MANIFEST.json for exact source paths, line spans and hashes. The new helper module uses the official [bcrypt API](https://pkg.go.dev/golang.org/x/crypto/bcrypt) and [pgx transaction API](https://pkg.go.dev/github.com/jackc/pgx/v5#TxOptions); actual installed versions are locked in go.mod/go.sum.
