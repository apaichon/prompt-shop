# TASK-0001: foundation handoff

Implementation: GPT / backend-dev-1. Required peer reviewer: Grok (pending).
Draft review: [PR #1](https://github.com/apaichon/prompt-shop/pull/1).
Worktree: `.worktrees/TASK-0001`; branch: `feature/TASK-0001-foundation`.

## Implemented

- Go Fiber public server with process health, bounded readiness, safe JSON errors, request IDs, graceful shutdown and a single feature-registration seam.
- PostgreSQL schema version 1, checksum-protected embedded migrations, separate operator CLI, role grants and a named-volume local Compose database.
- Versioned 60-published-product/eight-aisle sample, plus draft/archive fixtures; all demo destinations are connected to the entrance. Synthetic data, no real stock/price claims.
- Strict JSON import, Unicode NFKC/case-fold aliases, row-level validation, merged-map validation, store advisory lock, whole-batch rollback, immutable import versions, stable IDs and data version increments. Graph import is additive/upsert only; no delete API. Archive retires a product; omitted rows remain.
- OpenAPI and customer/backoffice/live/private ADK/Laya request/response fixtures. Private endpoints are not exposed on the public listener.

Search, route handlers, Svelte UI, actual Gemini/ADK/Laya, admin handlers and GCP deployment remain their assigned tasks. The default readiness mode checks ADK/Laya health and therefore stays 503 until they exist. Explicit local `foundation` mode checks schema/DB/seed/entrance only and sends `X-Readiness-Scope: foundation`; Cloud Run rejects this mode. Readiness does not require a constant published count after legitimate archive operations.

## Run locally

Requires Docker, Go 1.26.9 (pinned toolchain auto-download), and a free local port 55432. Use the task worktree. The `.env.example` passwords are disposable local examples only; deployment credentials must be separate.

```sh
rtk proxy cp .env.example .env
rtk proxy docker compose --env-file .env up -d db
# This Mac has a stale GOROOT; use its native Go and leave global shell config unchanged.
rtk proxy sh -c 'set -a; . ./.env; set +a; unset GOROOT; exec /opt/homebrew/bin/go run ./cmd/import -migrate -file data/demo-store.json'
rtk proxy sh -c 'docker compose exec -T db psql -U prompt_shop_operator -d prompt_shop -v ON_ERROR_STOP=1 < migrations/roles.sql'
rtk proxy sh -c 'docker compose exec -T db psql -U prompt_shop_operator -d prompt_shop -v ON_ERROR_STOP=1 < migrations/local_roles.sql'
rtk proxy sh -c 'set -a; . ./.env; set +a; unset GOROOT; exec /opt/homebrew/bin/go run ./cmd/server'
```

On other machines replace `/opt/homebrew/bin/go` with the installed Go executable. Visit `http://localhost:8080/healthz` and `/readyz`. The portal root currently returns JSON 404 because the frontend belongs to TASK-0004. Running the same import command twice returns `unchanged`; modifying a previously used version returns a row error and exit 1. New imports need a new lowercase `import_version`. `data/import.schema.json` describes required fields; nullable `map_node_id` explicitly represents an unmapped shelf. Initial seed has none.

`OPERATOR_DATABASE_URL` is used only by `cmd/import`; `DATABASE_URL` is used only by the public server. The server does not migrate or seed. It has a two-connection read-only pool; reserve two connections for backoffice and one for ticket admission so the future total remains five/instance. Apply `roles.sql` as an operator; provision production LOGIN roles/secrets separately. `local_roles.sql` is never for GCP. Migrations are forward-only and checksum-verified; do not modify 001 after adoption.

## Review / test commands

```sh
rtk proxy env -u GOROOT /opt/homebrew/bin/go test -race ./...
rtk proxy env -u GOROOT /opt/homebrew/bin/go vet ./...
rtk proxy env -u GOROOT /opt/homebrew/bin/go run golang.org/x/vuln/cmd/govulncheck@v1.9.0 ./...
rtk proxy python3 data/validate_contracts.py
```

Without `TEST_DATABASE_URL`, database integration tests explicitly skip. To reproduce TEST-0006, use a disposable database whose name ends in `_task1` (the integration test **drops its public schema**). Never point that variable at acceptance or user data. The recorded test used a task-owned container `prompt-shop-task1-db`, DB `prompt_shop_task1`, local port 55439 and named volume `prompt-shop-task1-data`. The task-owned test DB was left stopped after verification; if its container already exists, use `rtk proxy docker start prompt-shop-task1-db` instead of creating it again. Start a new container with the pinned Compose image and local test password `task1-disposable-only`, then:

```sh
rtk proxy docker run -d --name prompt-shop-task1-db -e POSTGRES_PASSWORD=task1-disposable-only -e POSTGRES_DB=prompt_shop_task1 -p 127.0.0.1:55439:5432 --mount type=volume,source=prompt-shop-task1-data,target=/var/lib/postgresql/data postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
```


```sh
rtk proxy env -u GOROOT 'TEST_DATABASE_URL=postgres://postgres:task1-disposable-only@127.0.0.1:55439/prompt_shop_task1?sslmode=disable' /opt/homebrew/bin/go test -race -count=1 -v ./...
rtk proxy env -u GOROOT GOOS=linux GOARCH=arm64 CGO_ENABLED=0 /opt/homebrew/bin/go build -o tmp/server ./cmd/server
rtk proxy python3 data/check_container.py
```

The last script tests a static non-root app container, role permissions, full-versus-foundation readiness, archive behavior, application restart, DB outage and named-volume persistence. It uses temporary local app images, not deployment Dockerfiles; production images are TASK-0005. Use GOARCH=amd64 instead for an amd64 Docker engine. JSON-schema checks need `jsonschema` 4.x; this is a validation dependency, not a runtime service dependency.

Evidence is in `sdlc/07-tests/evidence/TASK-0001/` and TEST-0006. The initial old Go/dependency scan failed; pins were updated before final verification. This local scan is not a container security audit or a GCP release test.

## Grok review request

Review this branch against TASK-0001, DES-0001's scoped foundation lock, ADR-0001 and TEST-0006. Focus on transactional import, complete graph validation, idempotent/concurrent version handling, least-privilege grants, readiness and schema/fixture consistency. Do not implement another task or edit shared contracts while this review is active. Record PASS or concrete required changes in TASK-0001. GPT's own verification is not a Grok approval. High-risk human review and CI remain merge gates.

TASK-0003 already has a separate user-authorized isolated worktree on the shared planning baseline; it still waits for foundation acceptance before integration. After foundation review/integration, TASK-0002 (Grok catalog/routing), TASK-0003 (GPT voice), TASK-0004 (Grok portal), TASK-0010 (Grok Laya), and TASK-0005 infrastructure preparation may proceed on their disjoint surfaces. Final integration still waits for their real implementations. Do not interpret this handoff as provider access or cloud-budget approval.

## Shared integration rules

- Feature packages expose constructors/registration functions; only foundation owner changes `cmd/server`, schema and Go dependency pins. `httpserver.Dependencies.Register` runs before the JSON 404 fallback. Private callbacks require a separate loopback listener.
- All catalog/admin/import writers use `importer.LockStore(ctx, tx, storeID)`, which locks `hashtextextended(storeID, 0)` for the transaction. Public reads use coherent snapshots; search ranking remains TASK-0002.
- Import raw SHA-256 includes whitespace: keep versioned files immutable. A different new version with identical semantic data records its receipt without bumping catalog/product/map versions. Alias order alone does not change a product.
- Existing-record errors caused by a map edit use index `-1`; incoming row indices are zero-based. Invalid imports print safe `{errors:[...]}` to stderr and exit nonzero.
- Health endpoints never expose DB addresses, secrets or error payloads. The full server uses bounded private health checks without provider calls. No request-body logger is installed.
- Browser/private examples live under `data/contracts/`; strict schemas do not replace session, turn, capability, Origin or CSRF authorization checks in later tasks.
