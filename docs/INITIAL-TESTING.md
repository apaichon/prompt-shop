# Initial testing from main

All ten tasks' current code is consolidated on `main` at the user's request. The merge preserves unfinished task/QA states. Begin with local component and portal testing; full shopper search/route/voice acceptance cannot pass yet because Task 2 public handlers and shared Go voice/catalog registration are incomplete. Laya's actual frozen accuracy is 19/40, required 36/40; native deployment CPU performance remains unqualified. No deployment occurred.

## Build and check the portal

Run from the repository root with Node 22.17+ and the existing lockfile:

```sh
rtk proxy npm --prefix web ci
rtk proxy npm --prefix web run check
rtk proxy npm --prefix web test
rtk proxy npm --prefix web run build
```

For an initial UI preview, run `rtk proxy npm --prefix web run dev` and open the URL it prints. This is a frontend development server; customer API failures are expected until the backend handlers are implemented and connected. The production portal is served by Go with `STATIC_DIR=web/build`.

## Local database and Go server

Docker and Go are required. Preserve any existing private `.env`; if absent, create it from `.env.example` and set local settings. The following uses the template's disposable local DB/user names. If you changed them, adapt the `psql` flags and matching local login setup. The import is an explicit local setup operation; use a local development database, not deployed or shared data.

The root Makefile manages local PostgreSQL. With Docker running, `rtk proxy make start` creates a private `.env` only if missing, starts/waits for the database, migrates, imports the seed and grants the read-only local login. Go, Python 3 and `rtk` must be installed. `stop` and `restart` retain data; `reset-data` deletes and recreates the local database volume, including custom products/sessions/logins. The helpers always use the fixed `prompt-shop` Compose project and a loopback import connection derived from `POSTGRES_*`, ignoring a remote `OPERATOR_DATABASE_URL`.

```sh
rtk proxy make start
rtk proxy make status
rtk proxy make stop
rtk proxy make restart
# Destructive: run only when you want a fresh local demo database.
rtk proxy make reset-data
```

Start the Go server separately after building the portal:

```sh
rtk proxy sh -c 'set -a; . ./.env; set +a; exec env -u GOROOT go run ./cmd/server'
```

The individual commands below remain available for diagnosis/manual setup:

```sh
rtk proxy docker compose --env-file .env up -d db
rtk proxy sh -c 'set -a; . ./.env; set +a; unset GOROOT; exec /opt/homebrew/bin/go run ./cmd/import -migrate -file data/demo-store.json'
rtk proxy sh -c 'docker compose --env-file .env exec -T db psql -U prompt_shop_operator -d prompt_shop -v ON_ERROR_STOP=1 < migrations/roles.sql'
rtk proxy sh -c 'docker compose --env-file .env exec -T db psql -U prompt_shop_operator -d prompt_shop -v ON_ERROR_STOP=1 < migrations/local_roles.sql'
rtk proxy sh -c 'set -a; . ./.env; set +a; unset GOROOT; exec /opt/homebrew/bin/go run ./cmd/server'
```

Use the installed Go executable in place of `/opt/homebrew/bin/go` on another machine. This Mac's commands unset a stale global GOROOT without changing shell configuration. Set `STATIC_DIR=web/build` after building the portal. The local template uses `READINESS_MODE=foundation`; that checks DB/schema/seed only and cannot qualify a deployment. Open `http://localhost:8080/`, `/healthz` and `/readyz`. In full mode readiness stays 503 until the private ADK/Laya dependencies are ready.

The portal can render from this server, but `/api/catalog/search`, map/route and public voice endpoints are not yet registered. Backoffice returns 503 until its separate DB login, PUBLIC_ORIGIN and bcrypt hash are configured together. Follow [protected backoffice setup](../internal/backoffice/README.md) for maintainer credentials, role grants, HTTPS/cookies and actual backend/browser verification. Do not use operator credentials for the public or backoffice service.

## Python modules and offline QA

The ADK and classifier have separate locked Python environments:

```sh
rtk proxy uv sync --project agent --frozen --python 3.11
rtk proxy uv sync --project intent --frozen --python 3.11
rtk proxy uv run --project agent --frozen pytest -q agent/tests
rtk proxy uv run --project agent --frozen python -m pytest -q intent/adapter_tests
rtk proxy uv run --project intent --frozen pytest -q intent/tests
rtk proxy python3 -m unittest discover -s tests/unit -v
rtk proxy python3 -m unittest discover -s deploy/tests -v
rtk proxy env -u GOROOT /opt/homebrew/bin/go test ./...
```

These cover local contracts and controlled lifecycle/failure fixtures. DB tests skip without explicitly configured disposable test DBs; see the owning module instructions before enabling them. Passing offline checks does not mean actual model, public API, native voice or cloud acceptance passed.

For actual Laya startup/download/env and evaluation, follow [intent/README.md](../intent/README.md). Its real 842 MB bundle is an ignored local asset, not in Git. The verified copy from Task 10 remains under `.worktrees/TASK-0010/intent/local/model-bundle`; you may set the server-only `LAYA_MODEL_PATH` to that absolute path rather than downloading it again. Set the same private LAYA_INTERNAL_TOKEN for ADK and Laya. Existing keys/env files were not copied, read or overwritten by the merge. For ADK native voice configuration, follow [agent/README.md](../agent/README.md); shared public Go wiring and real native provider testing are still required.

Proposal PPTX/PDF copies remain under the Task 7 worktree and are excluded from commits/pushes. Proposal sources and rehearsal instructions are in [docs/demo](demo/README.md). Cloud release tooling is in [deploy/RELEASE.md](../deploy/RELEASE.md), with acceptance guards preserved; initial local testing does not authorize cloud rollout.
