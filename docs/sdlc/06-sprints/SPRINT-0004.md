---
id: "SPRINT-0004"
type: "sprint"
title: "Deploy and verify final GCP prototype"
status: "proposed"
owner: "sdlc-orchestrator"
created: "2026-10-13"
updated: "2026-10-13"
start: "2026-10-16"
end: "2026-10-16"
goal: "Deploy and verify final GCP prototype"
committed: []
proposed_tasks: ["TASK-0008"]
completed: []
velocity_points: 0
coordination_mode: "sync"
related: ["ADR-0001", "DEP-0001", "DES-0001", "REQ-0004", "REQ-0005", "REQ-0006", "ROADMAP-0001", "TASK-0005", "TASK-0006", "TASK-0008", "TASK-0010", "TEST-0004", "TEST-0012"]
---

# SPRINT-0004: Deploy and verify final GCP prototype

## Goal
Deploy and verify final GCP prototype. All dates use Asia/Bangkok. This is a one-day proposed sprint; no task is yet approved or committed.

## Proposed commitment
- [TASK-0008](../05-tasks/TASK-0008.md)

## Capacity and coordination
There is no local velocity history or retrospective. Config lists five delivery-agent slots; this is not five confirmed humans. Effort estimates are provisional and must be recalibrated after the first vertical slice. No historical points or throughput is invented.

- Goal: ROADMAP-0001.
- Mode: **sync**.
- Resync trigger: any approved contract/schema change, shared frontend layout conflict or failing integration; return to sync until resolved.
- Proposed cutoff17:00 Bangkok. Only release-blocking fixes. No schema-breaking changes or new product features.

## Exit and carry-over
Record actual evidence from linked tests before reporting completion. Unfinished core work carries forward visibly and triggers scope cuts; do not mark tasks done because their planned date has passed. Protect 16 October deployment by cutting extra languages, recipes, vector work and visual polish first. If core ADK/Gemini Live 3.8/Laya/cloud/auth is still blocked at 15 October 18:00, report deadline risk immediately rather than relabeling a local or typed-only demo as complete.

## GPT / Grok execution

| Task | Builder | Reviewer |
|---|---|---|
| [TASK-0008](../05-tasks/TASK-0008.md) | GPT | Grok |

Follow [MODEL-ALLOCATION.md](../../MODEL-ALLOCATION.md) for exclusive file ownership and handoff order. One active builder per task; additional parallel sessions must have disjoint paths. All assignments remain proposed.

## Related work

These links identify the inputs and verification for this sprint; proposed assignments do not claim approval or completion.

| Task | Requirements | Design / ADR | Verification | Prerequisites |
|---|---|---|---|---|
| [TASK-0008](../05-tasks/TASK-0008.md) | [REQ-0004](../02-requirements/REQ-0004.md), [REQ-0005](../02-requirements/REQ-0005.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0004](../07-tests/TEST-0004.md) | [TASK-0005](../05-tasks/TASK-0005.md), [TASK-0006](../05-tasks/TASK-0006.md) |

Deployment plan: [DEP-0001](../08-deployments/DEP-0001.md).
