# prompt-shop

A single hypermarket portal with an English-first Gemini Live 3.8 voice-to-voice item finder using Google ADK and Laya intent classification, shelf directions and a protected catalog backoffice. Extra languages, recipes and vector search follow the core prototype.

## Prototype plan

Deploy to GCP by **16 October 2026**; rehearse on **17 October**; submit on **18 October** (Asia/Bangkok).

- [MVP plan and daily schedule](docs/MVP-PLAN.md)
- [Proposed SDLC review pack](docs/sdlc/REVIEW.md)
- [Selected Monti Jarvis code and provenance](references/monti-jarvis/README.md)

Current state: all ten tasks' current source snapshots are consolidated for initial local testing. The portal and protected backoffice are implemented; public shopper catalog/routes and Go voice registration remain incomplete, Laya accuracy qualification failed, and the candidate is not deployed. Start with [initial local testing](docs/INITIAL-TESTING.md); the [source consolidation record](docs/INTEGRATION-ALL-TASKS-2026-10-14.md) preserves acceptance blockers.

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
