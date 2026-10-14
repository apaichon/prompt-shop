# AGENTS.md — prompt-shop

A single hypermarket portal with an English-first Gemini Live 3.8 voice-to-voice item finder using Google ADK and Laya intent classification, shelf directions and a protected catalog backoffice. Additional languages, recipes and vector search follow the core prototype.

Tech stack: Svelte, Gemini Live 3.8, Google ADK (Python), Laya, Go Fiber, PostgreSQL, pg-vector, Docker, Google Cloud Platform.

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

## GPT / Grok task routing

Read [docs/MODEL-ALLOCATION.md](docs/MODEL-ALLOCATION.md) before claiming implementation work. GPT builds TASK-0001, TASK-0003, TASK-0004, TASK-0005, TASK-0008 and TASK-0009. Grok builds TASK-0002, TASK-0006, TASK-0007 and TASK-0010. Each task's `implementation_model` and `review_model` select the assistants; `owner` remains the accountable SDLC role. Use one task worktree and respect exclusive file surfaces. GPT coordinates shared contracts/wiring and integration; reviewers request changes rather than editing another builder's active files. No Grok client or automatic dispatch is configured by this allocation.

## Document conventions

See `CONVENTIONS.md`.

## Git workflow

GitFlow + one worktree per task. **Canonical reference: `GIT_WORKFLOW.md`.** Codex does not auto-load skills the way Claude does; instead, every agent above reads `GIT_WORKFLOW.md` and runs the documented commands directly (they're plain `git` / `gh`). Coordination across agents uses **sync / parallel / resync** modes — declared in the sprint doc by `pm-agent`, arbitrated by `sdlc-orchestrator`.

## Hook parity

Codex does not auto-register the propagation hook. Run propagation manually:

```
node scripts/sdlc-propagate.js path/to/changed/doc.md
```

Or after a session, run:

```
node scripts/sdlc-graph.js
```

to refresh the dependency graph.

## Local command convention

Read `/Users/apaichon/.codex/RTK.md`; prefix all shell commands with `rtk`.
