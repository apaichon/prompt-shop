---
id: "SPRINT-0003"
type: "sprint"
title: "Finish minimal backoffice and freeze verified English scope"
status: "proposed"
owner: "sdlc-orchestrator"
created: "2026-10-13"
updated: "2026-10-13"
start: "2026-10-15"
end: "2026-10-15"
goal: "Finish minimal backoffice and freeze verified English scope"
committed: []
proposed_tasks: ["TASK-0009", "TASK-0006"]
completed: []
velocity_points: 0
coordination_mode: "sync"
related: ["ADR-0001", "DES-0001", "REQ-0001", "REQ-0002", "REQ-0003", "REQ-0004", "REQ-0005", "REQ-0006", "ROADMAP-0001", "TASK-0001", "TASK-0002", "TASK-0003", "TASK-0004", "TASK-0005", "TASK-0006", "TASK-0009", "TASK-0010", "TEST-0001", "TEST-0002", "TEST-0003", "TEST-0005", "TEST-0012"]
---

# SPRINT-0003: Finish minimal backoffice and freeze verified English scope

## Goal
Finish minimal backoffice and freeze verified English scope. All dates use Asia/Bangkok. This is a one-day proposed sprint; no task is yet approved or committed.

## Proposed commitment
- [TASK-0009](../05-tasks/TASK-0009.md)
- [TASK-0006](../05-tasks/TASK-0006.md)

## Capacity and coordination
There is no local velocity history or retrospective. Config lists five delivery-agent slots; this is not five confirmed humans. Effort estimates are provisional and must be recalibrated after the first vertical slice. No historical points or throughput is invented.

- Goal: ROADMAP-0001.
- Mode: **sync**.
- Resync trigger: any approved contract/schema change, shared frontend layout conflict or failing integration; return to sync until resolved.
- TASK-0009 may prepare after the 14 October customer shell; finish before QA acceptance. Run QA after all core integrations. Disable all stretch work if core gates are not green.

## Exit and carry-over
Record actual evidence from linked tests before reporting completion. Unfinished core work carries forward visibly and triggers scope cuts; do not mark tasks done because their planned date has passed. Protect 16 October deployment by cutting extra languages, recipes, vector work and visual polish first. If core ADK/Gemini Live 3.8/Laya/cloud/auth is still blocked at 15 October 18:00, report deadline risk immediately rather than relabeling a local or typed-only demo as complete.

## GPT execution

| Task | Builder | Reviewer |
|---|---|---|
| [TASK-0009](../05-tasks/TASK-0009.md) | GPT | GPT |
| [TASK-0006](../05-tasks/TASK-0006.md) | GPT | GPT |

Follow [MODEL-ALLOCATION.md](../../MODEL-ALLOCATION.md) for exclusive file ownership and handoff order. One active builder per task; additional parallel sessions must have disjoint paths. All assignments remain proposed.

## Related work

These links identify the inputs and verification for this sprint; proposed assignments do not claim approval or completion.

| Task | Requirements | Design / ADR | Verification | Prerequisites |
|---|---|---|---|---|
| [TASK-0009](../05-tasks/TASK-0009.md) | [REQ-0001](../02-requirements/REQ-0001.md), [REQ-0005](../02-requirements/REQ-0005.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0005](../07-tests/TEST-0005.md) | [TASK-0001](../05-tasks/TASK-0001.md), [TASK-0004](../05-tasks/TASK-0004.md) |
| [TASK-0006](../05-tasks/TASK-0006.md) | [REQ-0001](../02-requirements/REQ-0001.md), [REQ-0002](../02-requirements/REQ-0002.md), [REQ-0003](../02-requirements/REQ-0003.md), [REQ-0004](../02-requirements/REQ-0004.md), [REQ-0005](../02-requirements/REQ-0005.md), [REQ-0006](../02-requirements/REQ-0006.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0001](../07-tests/TEST-0001.md), [TEST-0002](../07-tests/TEST-0002.md), [TEST-0003](../07-tests/TEST-0003.md), [TEST-0005](../07-tests/TEST-0005.md), [TEST-0012](../07-tests/TEST-0012.md) | [TASK-0002](../05-tasks/TASK-0002.md), [TASK-0003](../05-tasks/TASK-0003.md), [TASK-0004](../05-tasks/TASK-0004.md), [TASK-0005](../05-tasks/TASK-0005.md), [TASK-0009](../05-tasks/TASK-0009.md), [TASK-0010](../05-tasks/TASK-0010.md) |


## TASK-0009 local build — 14 October 2026

GPT built the protected Go/PostgreSQL backoffice and Svelte editor in feature/TASK-0009-backoffice with local foundation/customer-shell dependency inputs. Automated backoffice, responsive/accessibility and customer regression checks pass. TEST-0005/TASK-0009 remain blocked for actual public catalog integration, manual/deployed persistence evidence and approval gates. Read internal/backoffice/README.md for serialized config/static and TASK-0002/0005/0006 handoffs. No task completion or deployed acceptance is inferred.


## Requested source consolidation — 2026-10-14

User instructed merging TASK-0001/0002/0003/0004/0005/0009/0006 into main. Integration coordinator runs sync/resync in INTEGRATION-20261014, preserves feature history and execution evidence, and resolves shared allocation/docs/portal conflicts. [Integration ledger](../../INTEGRATION-2026-10-14.md) records snapshots, narrow preparation fixes and actual checks. This source merge does not change incomplete task/test/release states or constitute a deployment.
