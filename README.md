# prompt-shop

A single hypermarket portal with an English-first Gemini Live 3.8 voice-to-voice item finder using Google ADK and Laya intent classification, shelf directions and a protected catalog backoffice. Extra languages, recipes and vector search follow the core prototype.

## Prototype plan

Deploy to GCP by **16 October 2026**; rehearse on **17 October**; submit on **18 October** (Asia/Bangkok).

- [MVP plan and daily schedule](docs/MVP-PLAN.md)
- [Proposed SDLC review pack](docs/sdlc/REVIEW.md)
- [Selected Monti Jarvis code and provenance](references/monti-jarvis/README.md)

Current state: all ten tasks' source is consolidated. Local typed search, map/routes and the native Gemini/ADK/Laya voice path are connected; use `rtk proxy make mvp-start` for the complete local stack. A synthetic browser voice request returned a real product/route and native audio. Laya accuracy qualification remains failed and the candidate is not deployed. Start with [initial local testing](docs/INITIAL-TESTING.md); [voice-start diagnosis](docs/VOICE-START-FIX-2026-10-16.md) records the fix and its limits.

## Tech stack

SvelteKit (static Svelte portal), Go Fiber, PostgreSQL, Docker, Google Cloud Platform. pgvector is deferred until the core concept works.

## Team

backend×2, frontend×1, qa×1, devops×1 (total: 5)

## SDLC

See `CONVENTIONS.md` for the numbered document layout and `docs/sdlc/_templates/` for blank artifact templates. Begin with `01-roadmap`, capture 5W1H requirements in `02-requirements`, and track executable work in `05-tasks`.

Run `node scripts/sdlc-graph.js` to generate the dependency graph.

## Git workflow

GitFlow (`main` / `develop` / `feature/*` / `release/*` / `hotfix/*`) with **one worktree per task** under `.worktrees/<TASK-ID>/`. Read `GIT_WORKFLOW.md` once for the rules; agents invoke the `git-workflow` skill (`.claude/skills/git-workflow/SKILL.md`) for every git action. Coordination across agents uses **sync / parallel / resync** modes — see `CONVENTIONS.md`.

## Roster

Agents are generated for both Codex (`agents/`) and Claude Code (`.claude/agents/`).

- `pm-agent` — Roadmap, requirements, task decomposition and daily sprint planning.
- `architect-agent` — Solution contracts, architecture decisions and review locks.
- `backend-dev-agent-1` — Catalog, data/imports, routes and backoffice lead; shared server/schema wiring.
- `backend-dev-agent-2` — Python ADK Live runtime, Laya intent classification, gateway tools and session recovery.
- `frontend-dev-agent` — Single customer/backoffice Svelte portal and accessible map UX.
- `qa-agent` — Catalog, voice, routing, authorization and release acceptance.
- `devops-agent` — GCP staging, deployment, secrets, monitoring and rollback.
- `docs-agent` — Review consistency, reuse provenance and demo documentation.
- `sdlc-orchestrator` — Dependency coordination, graph export and review handoffs.

The backend artifact owners are `backend-dev-1` and `backend-dev-2`, matching each brief. Other specialized roles are not configured for this prototype.

Helper skills in `.claude/skills/`: `adr-writer`, `code-reviewer`, `deploy-runner`, `design-author`, `docs-updater`, `git-workflow`, `incident-responder`, `requirement-author`, `risk-review`, `roadmap-author`, `sdlc-graph-export`, `sprint-planner`, `sprint-retrospective`, `task-author`, `task-implementer`, `task-progress-update`, `test-runner`, `test-writer`.

## Optional: enable auto-propagation hook

The skill ships an opt-in PostToolUse hook that auto-propagates status changes across linked SDLC docs. To enable, copy the snippet from `.claude/settings.snippet.json` into your `.claude/settings.json`.

## GPT collaboration

The [task allocation plan](docs/MODEL-ALLOCATION.md) assigns all ten tasks to GPT, with file boundaries, a separate review pass and handoff prompts. Assignment metadata is recorded in each task. Gemini Live 3.8, ADK and Laya remain the application runtime.

## Foundation implementation

TASK-0001 database/import and health setup is documented in [TASK-0001-HANDOFF.md](docs/TASK-0001-HANDOFF.md). That historical task handoff predates the consolidated portal, backoffice and classifier source; use the initial testing guide for the current combined checkout.

Backoffice setup and verification: [internal/backoffice/README.md](internal/backoffice/README.md).

## Local infrastructure commands

For a functional voice MVP, configure `agent/.env` and the pinned Laya bundle as described in [initial testing](docs/INITIAL-TESTING.md), then use `rtk proxy make mvp-start`. `mvp-status`, `mvp-stop` and `mvp-restart` manage the three application processes; stop retains PostgreSQL. The commands below manage PostgreSQL only.

Run from the repository root with Docker running, Docker Compose, Go, Python 3 and `rtk` installed:

```sh
rtk proxy make start
rtk proxy make stop
rtk proxy make restart
rtk proxy make reset-data
```

`start` creates a private `.env` from `.env.example` only when missing, starts PostgreSQL, waits for readiness, applies migrations, imports the demo seed and grants the local read-only login. Repeated imports of the same seed are idempotent. `stop` and `restart` retain the database volume; `restart` does not reseed it. `reset-data` deletes this project's local database volume, then rebuilds the schema/seed/login. It removes custom data, maintainer sessions and extra database logins; recreate optional backoffice logins afterward. Stop any app using this database before resetting it.

Use `rtk proxy make status`, `rtk proxy make logs` or `rtk proxy make help` for inspection. The aliases `infra-start`, `infra-stop`, `infra-restart` and `infra-reset-data` are also available. These commands manage the fixed `prompt-shop` Compose project and its PostgreSQL service, not the Go server, portal, ADK, Laya or GCP. Imports always use loopback and the local `POSTGRES_*` settings, ignoring a caller's `OPERATOR_DATABASE_URL`. If you customize `.env`, keep `DATABASE_URL` consistent with your local reader login; the supplied login script creates `prompt_shop_reader` with the development password from the template.
