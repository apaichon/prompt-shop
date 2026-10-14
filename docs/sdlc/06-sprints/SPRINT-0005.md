---
id: "SPRINT-0005"
type: "sprint"
title: "Rehearse and package for submission"
status: "proposed"
owner: "sdlc-orchestrator"
created: "2026-10-13"
updated: "2026-10-13"
start: "2026-10-17"
end: "2026-10-17"
goal: "Rehearse and package for submission"
committed: []
proposed_tasks: ["TASK-0007"]
completed: []
velocity_points: 0
coordination_mode: "sync"
related: ["ADR-0001", "DES-0001", "REQ-0004", "REQ-0006", "ROADMAP-0001", "TASK-0007", "TASK-0008", "TASK-0010", "TEST-0011", "TEST-0012"]
---

# SPRINT-0005: Rehearse and package for submission

## Goal
Rehearse and package for submission. All dates use Asia/Bangkok. This is a one-day proposed sprint; no task is yet approved or committed.

## Proposed commitment
- [TASK-0007](../05-tasks/TASK-0007.md)

## Capacity and coordination
There is no local velocity history or retrospective. Config lists five delivery-agent slots; this is not five confirmed humans. Effort estimates are provisional and must be recalibrated after the first vertical slice. No historical points or throughput is invented.

- Goal: ROADMAP-0001.
- Mode: **sync**.
- Resync trigger: any approved contract/schema change, shared frontend layout conflict or failing integration; return to sync until resolved.
- Verify final demo and backup video. User submits18October; exact format/time still open. Optional languages cannot destabilize the frozen release.

## Exit and carry-over
Record actual evidence from linked tests before reporting completion. Unfinished core work carries forward visibly and triggers scope cuts; do not mark tasks done because their planned date has passed. Protect 16 October deployment by cutting extra languages, recipes, vector work and visual polish first. If core ADK/Gemini Live 3.8/Laya/cloud/auth is still blocked at 15 October 18:00, report deadline risk immediately rather than relabeling a local or typed-only demo as complete.

## GPT execution

| Task | Builder | Reviewer |
|---|---|---|
| [TASK-0007](../05-tasks/TASK-0007.md) | GPT | GPT |

Follow [MODEL-ALLOCATION.md](../../MODEL-ALLOCATION.md) for exclusive file ownership and handoff order. One active builder per task; additional parallel sessions must have disjoint paths. All assignments remain proposed.

## Related work

These links identify the inputs and verification for this sprint; proposed assignments do not claim approval or completion.

| Task | Requirements | Design / ADR | Verification | Prerequisites |
|---|---|---|---|---|
| [TASK-0007](../05-tasks/TASK-0007.md) | [REQ-0004](../02-requirements/REQ-0004.md) | [DES-0001](../03-designs/DES-0001.md), [ADR-0001](../04-adrs/ADR-0001.md) | [TEST-0011](../07-tests/TEST-0011.md) | [TASK-0008](../05-tasks/TASK-0008.md) |
