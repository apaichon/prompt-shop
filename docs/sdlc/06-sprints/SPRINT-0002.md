---
id: "SPRINT-0002"
type: "sprint"
title: "Build and deploy the first real English vertical slice"
status: "proposed"
owner: "sdlc-orchestrator"
created: "2026-10-13"
updated: "2026-10-13"
start: "2026-10-14"
end: "2026-10-14"
goal: "Build and deploy the first real English vertical slice"
committed: []
proposed_tasks: ["TASK-0002", "TASK-0003", "TASK-0004", "TASK-0005", "TASK-0010"]
completed: []
velocity_points: 0
coordination_mode: "parallel"
related: ["ADR-0001", "DEP-0001", "DES-0001", "REQ-0001", "REQ-0002", "REQ-0003", "REQ-0004", "REQ-0005", "REQ-0006", "ROADMAP-0001", "TASK-0001", "TASK-0002", "TASK-0003", "TASK-0004", "TASK-0005", "TASK-0010", "TEST-0007", "TEST-0008", "TEST-0009", "TEST-0010", "TEST-0012"]
---

# SPRINT-0002: Build and deploy the first real English vertical slice

## Goal
Build and deploy the first real English vertical slice. All dates use Asia/Bangkok. This is a one-day proposed sprint; no task is yet approved or committed.

## Proposed commitment
- [TASK-0002](../05-tasks/TASK-0002.md)
- [TASK-0003](../05-tasks/TASK-0003.md)
- [TASK-0004](../05-tasks/TASK-0004.md)
- [TASK-0005](../05-tasks/TASK-0005.md)
- [TASK-0010](../05-tasks/TASK-0010.md)

## Capacity and coordination
There is no local velocity history or retrospective. Config lists five delivery-agent slots; this is not five confirmed humans. Effort estimates are provisional and must be recalibrated after the first vertical slice. No historical points or throughput is invented.

- Goal: ROADMAP-0001.
- Mode: **parallel**.
- Resync trigger: any approved contract/schema change, shared frontend layout conflict or failing integration; return to sync until resolved.
- Parallel only on DES-0001 disjoint module surfaces. Shared router, schema and dependency files serialize through backend-dev-1. UI can use approved fixtures while backend is built; staging exit requires real APIs and actual gemini-3.8-live native audio with catalog/route tools. ADK TASK-0003 is 8–14 hours, Laya TASK-0010 is 4–7 hours (Grok, alongside GPT TASK-0003 after contract freeze), and portal TASK-0004 is 6–9 hours; verify capacity after the 13 October spike.

## Exit and carry-over
Record actual evidence from linked tests before reporting completion. Unfinished core work carries forward visibly and triggers scope cuts; do not mark tasks done because their planned date has passed. Protect 16 October deployment by cutting extra languages, recipes, vector work and visual polish first. If core ADK/Gemini Live 3.8/Laya/cloud/auth is still blocked at 15 October 18:00, report deadline risk immediately rather than relabeling a local or typed-only demo as complete.

## GPT / Grok execution

| Task | Builder | Reviewer |
|---|---|---|
| [TASK-0002](../05-tasks/TASK-0002.md) | Grok | GPT |
| [TASK-0003](../05-tasks/TASK-0003.md) | GPT | Grok |
| [TASK-0004](../05-tasks/TASK-0004.md) | Grok | GPT |
| [TASK-0005](../05-tasks/TASK-0005.md) | GPT | Grok |
| [TASK-0010](../05-tasks/TASK-0010.md) | Grok | GPT |

Follow [MODEL-ALLOCATION.md](../../MODEL-ALLOCATION.md) for exclusive file ownership and handoff order. One active builder per task; additional parallel sessions must have disjoint paths. All assignments remain proposed.

## Related work

These links identify the inputs and verification for this sprint; proposed assignments do not claim approval or completion.

| Task | Requirements | Design / ADR | Verification | Prerequisites |
|---|---|---|---|---|
| [TASK-0002](../05-tasks/TASK-0002.md) | [REQ-0001](../02-requirements/REQ-0001.md), [REQ-0003](../02-requirements/REQ-0003.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0007](../07-tests/TEST-0007.md) | [TASK-0001](../05-tasks/TASK-0001.md) |
| [TASK-0003](../05-tasks/TASK-0003.md) | [REQ-0002](../02-requirements/REQ-0002.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0008](../07-tests/TEST-0008.md) | [TASK-0001](../05-tasks/TASK-0001.md) |
| [TASK-0004](../05-tasks/TASK-0004.md) | [REQ-0001](../02-requirements/REQ-0001.md), [REQ-0002](../02-requirements/REQ-0002.md), [REQ-0003](../02-requirements/REQ-0003.md), [REQ-0005](../02-requirements/REQ-0005.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0009](../07-tests/TEST-0009.md) | [TASK-0001](../05-tasks/TASK-0001.md) |
| [TASK-0005](../05-tasks/TASK-0005.md) | [REQ-0004](../02-requirements/REQ-0004.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0010](../07-tests/TEST-0010.md) | [TASK-0001](../05-tasks/TASK-0001.md) |
| [TASK-0010](../05-tasks/TASK-0010.md) | [REQ-0006](../02-requirements/REQ-0006.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0012](../07-tests/TEST-0012.md) | [TASK-0001](../05-tasks/TASK-0001.md) |

Deployment plan: [DEP-0001](../08-deployments/DEP-0001.md).

## Synchronization checkpoints

After accepted TASK-0001, TASK-0002/0003/0004/0005/0010 may start on disjoint surfaces. Fixture-based feature work can proceed independently; TASK-0005 cannot finish until actual catalog, ADK voice, customer UI and Laya integrate and TEST-0010 passes. TASK-0009 waits for accepted TASK-0004, and final TASK-0006 waits for staging plus all features. See [the execution matrix](../../MODEL-ALLOCATION.md#synchronization-and-parallel-work) for start gates, completion gates and the default two-session schedule.
