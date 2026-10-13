# Proposed SDLC review pack

The user brief, sample data, required Gemini Live 3.8 native voice-to-voice through Google ADK, Laya intent classification, English-first priority, same-portal backoffice and selected Monti reuse are captured in [MVP-PLAN.md](../MVP-PLAN.md). Deployment is due 16 October 2026; submission 18 October, Asia/Bangkok. The proposed 17:00 deployment cutoff is an assumption. All artifacts are proposed; implementation lock unsigned.

## Artifact review

| ID | Title | Owner | Risk | Dependencies / links | Recommendation |
|---|---|---|---|---|---|
| [ROADMAP-0001](01-roadmap/ROADMAP-0001-mvp-demo.md) | Deploy the item-finding voice prototype by 16 October | pm-agent | high | REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006 | Review scope and outcome |
| [REQ-0001](02-requirements/REQ-0001.md) | Catalog-grounded product lookup | pm-agent | high | DES-0001, ROADMAP-0001, TEST-0001 | Review scope and outcome |
| [REQ-0002](02-requirements/REQ-0002.md) | Gemini Live 3.8 native voice-to-voice | pm-agent | high | DES-0001, REQ-0006, ROADMAP-0001, TEST-0002 | Review scope and outcome |
| [REQ-0003](02-requirements/REQ-0003.md) | Walkable directions to the selected shelf | pm-agent | medium | DES-0001, ROADMAP-0001, TEST-0003 | Review scope and outcome |
| [REQ-0004](02-requirements/REQ-0004.md) | GCP deployment and submission readiness | pm-agent | high | DES-0001, ROADMAP-0001, TEST-0004, TEST-0011 | Review scope and outcome |
| [REQ-0005](02-requirements/REQ-0005.md) | Customer and catalog backoffice in one portal | pm-agent | high | DES-0001, REQ-0001, REQ-0004, ROADMAP-0001, TEST-0005 | Review scope and outcome |
| [REQ-0006](02-requirements/REQ-0006.md) | Required Laya intent classification through ADK | pm-agent | high | DES-0001, REQ-0002, REQ-0004, ROADMAP-0001, TEST-0002, TEST-0012 | Review scope and outcome |
| [DES-0001](03-designs/DES-0001.md) | English voice-to-shelf prototype on GCP | architect-agent | high | ADR-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006, ROADMAP-0001, TEST-0001, TEST-0002, TEST-0003, TEST-0004, TEST-0005, TEST-0012 | Review contracts |
| [ADR-0001](04-adrs/ADR-0001.md) | Use ADK Gemini 3.8 Live and private Laya intent inference with authoritative Go tools | architect-agent | Not separately rated | DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006 | Review decision |
| [TASK-0001](05-tasks/TASK-0001.md) | Foundation, sample catalog and import | backend-dev-1 | high | DES-0001, REQ-0001, TEST-0006 | Review work and dependencies |
| [TASK-0002](05-tasks/TASK-0002.md) | Catalog lookup and walkable route API | backend-dev-1 | medium | DES-0001, REQ-0001, REQ-0003, TASK-0001, TEST-0007 | Review work and dependencies |
| [TASK-0003](05-tasks/TASK-0003.md) | ADK Gemini Live 3.8 conversation and gateway | backend-dev-2 | high | DES-0001, REQ-0002, REQ-0006, TASK-0001, TASK-0010, TEST-0008 | Review work and dependencies |
| [TASK-0004](05-tasks/TASK-0004.md) | Unified portal customer search and map | frontend-dev | medium | DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0005, TASK-0001, TEST-0009 | Review work and dependencies |
| [TASK-0005](05-tasks/TASK-0005.md) | Early GCP staging and environment proof | devops-agent | high | DES-0001, REQ-0004, REQ-0006, TASK-0001, TASK-0010, TEST-0010 | Review work and dependencies |
| [TASK-0006](05-tasks/TASK-0006.md) | Integrated acceptance and hardening | qa-agent | high | DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006, TASK-0002, TASK-0003, TASK-0004, TASK-0005, TASK-0009, TASK-0010, TEST-0001, TEST-0002, TEST-0003, TEST-0005, TEST-0012 | Review work and dependencies |
| [TASK-0007](05-tasks/TASK-0007.md) | Demo rehearsal and submission package | docs-agent | medium | DES-0001, REQ-0004, TASK-0008, TEST-0011 | Review work and dependencies |
| [TASK-0008](05-tasks/TASK-0008.md) | Final GCP release and rollback verification | devops-agent | high | DES-0001, REQ-0004, REQ-0005, TASK-0005, TASK-0006, TEST-0004 | Review work and dependencies |
| [TASK-0009](05-tasks/TASK-0009.md) | Protected catalog backoffice from selected Monti patterns | backend-dev-1 | high | DES-0001, REQ-0001, REQ-0005, TASK-0001, TASK-0004, TEST-0005 | Review work and dependencies |
| [TASK-0010](05-tasks/TASK-0010.md) | Laya classifier and ADK intent tool | backend-dev-2 | high | DES-0001, REQ-0006, TASK-0001, TEST-0012 | Review work and dependencies |
| [SPRINT-0001](06-sprints/SPRINT-0001.md) | Freeze core contracts and prove feasibility | sdlc-orchestrator | Not separately rated | ADR-0001, DES-0001, REQ-0001, REQ-0006, ROADMAP-0001, TASK-0001, TASK-0003, TASK-0010, TEST-0006, TEST-0012 | Review scope and capacity |
| [SPRINT-0002](06-sprints/SPRINT-0002.md) | Build and deploy the first real English vertical slice | sdlc-orchestrator | Not separately rated | ADR-0001, DEP-0001, DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006, ROADMAP-0001, TASK-0001, TASK-0002, TASK-0003, TASK-0004, TASK-0005, TASK-0010, TEST-0007, TEST-0008, TEST-0009, TEST-0010, TEST-0012 | Review scope and capacity |
| [SPRINT-0003](06-sprints/SPRINT-0003.md) | Finish minimal backoffice and freeze verified English scope | sdlc-orchestrator | Not separately rated | ADR-0001, DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006, ROADMAP-0001, TASK-0001, TASK-0002, TASK-0003, TASK-0004, TASK-0005, TASK-0006, TASK-0009, TASK-0010, TEST-0001, TEST-0002, TEST-0003, TEST-0005, TEST-0012 | Review scope and capacity |
| [SPRINT-0004](06-sprints/SPRINT-0004.md) | Deploy and verify final GCP prototype | sdlc-orchestrator | Not separately rated | ADR-0001, DEP-0001, DES-0001, REQ-0004, REQ-0005, REQ-0006, ROADMAP-0001, TASK-0005, TASK-0006, TASK-0008, TASK-0010, TEST-0004, TEST-0012 | Review scope and capacity |
| [SPRINT-0005](06-sprints/SPRINT-0005.md) | Rehearse and package for submission | sdlc-orchestrator | Not separately rated | ADR-0001, DES-0001, REQ-0004, REQ-0006, ROADMAP-0001, TASK-0007, TASK-0008, TASK-0010, TEST-0011, TEST-0012 | Review scope and capacity |
| [TEST-0001](07-tests/TEST-0001.md) | Catalog correctness and transactional import | qa-agent | high | DES-0001, REQ-0001, TASK-0001, TEST-0002 | Review evidence plan; not executed |
| [TEST-0002](07-tests/TEST-0002.md) | Required Gemini Live English conversation and recovery | qa-agent | high | DES-0001, REQ-0001, REQ-0002, REQ-0006, TASK-0004, TASK-0010, TEST-0001, TEST-0004, TEST-0012 | Review evidence plan; not executed |
| [TEST-0003](07-tests/TEST-0003.md) | Walkable shelf routes and accessible map experience | qa-agent | high | DES-0001, REQ-0003, TASK-0002, TEST-0001, TEST-0004 | Review evidence plan; not executed |
| [TEST-0004](07-tests/TEST-0004.md) | Final GCP release, rollback and performance | qa-agent | high | DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006, TASK-0005, TASK-0006, TEST-0001, TEST-0002, TEST-0003, TEST-0005, TEST-0010, TEST-0011, TEST-0012 | Review evidence plan; not executed |
| [TEST-0005](07-tests/TEST-0005.md) | Single portal and protected catalog maintenance | qa-agent | high | DES-0001, REQ-0005, TASK-0001, TASK-0002, TASK-0004, TEST-0001, TEST-0004 | Review evidence plan; not executed |
| [TEST-0006](07-tests/TEST-0006.md) | Foundation and import integration gate | qa-agent | high | DES-0001, REQ-0001, TEST-0001 | Review evidence plan; not executed |
| [TEST-0007](07-tests/TEST-0007.md) | Catalog and routing API integration gate | qa-agent | high | DES-0001, REQ-0001, REQ-0003, TEST-0001, TEST-0003, TEST-0006 | Review evidence plan; not executed |
| [TEST-0008](07-tests/TEST-0008.md) | ADK Live runtime, protocol and required-model smoke gate | qa-agent | high | DES-0001, REQ-0001, REQ-0002, REQ-0003, TEST-0002 | Review evidence plan; not executed |
| [TEST-0009](07-tests/TEST-0009.md) | Customer portal Live-session fixture and accessibility gate | qa-agent | medium | DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0005, TEST-0001, TEST-0002, TEST-0003, TEST-0005 | Review evidence plan; not executed |
| [TEST-0010](07-tests/TEST-0010.md) | Early GCP English vertical-slice smoke | qa-agent | high | DES-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0006, TASK-0002, TASK-0003, TASK-0004, TASK-0010, TEST-0004 | Review evidence plan; not executed |
| [TEST-0011](07-tests/TEST-0011.md) | Rehearsal and submission-package readiness | qa-agent | medium | DES-0001, REQ-0004, TASK-0008, TEST-0004 | Review evidence plan; not executed |
| [TEST-0012](07-tests/TEST-0012.md) | Laya intent classification through ADK | qa-agent | high | DES-0001, REQ-0006, TASK-0003, TEST-0002, TEST-0008 | Review evidence plan; not executed |
| [DEP-0001](08-deployments/DEP-0001.md) | GCP prototype deployment and rollback plan | devops-agent | critical | DES-0001, REQ-0001, REQ-0002, REQ-0003, REQ-0004, REQ-0005, REQ-0006, ROADMAP-0001, TEST-0001, TEST-0002, TEST-0003, TEST-0004, TEST-0005, TEST-0010, TEST-0012 | Review cloud details; not deployed |

## Operational readiness

[READINESS.md](09-operations/READINESS.md) is a runbook/readiness draft, not an invented incident. It covers cloud prerequisites, session/data checks, smoke and recovery.

## Validation evidence

- Dependency graph generated with 37 artifact nodes; all references resolve. No artifact is marked approved, in progress or done.
- Source snapshot: 20 files/excerpts copied with exact source hashes/line provenance and MIT license.
- Copied standalone Go static-serving and credential-redaction test suites passed. These are source-helper checks only.
- Runtime portal, ADK/Gemini exchange, Laya installation/inference, PostgreSQL integration, acceptance benchmarks and GCP deployment have not run.

## Questions and approval boundary

Cloud project/billing/budget, region/provider qualification, demo device/access and submission format/cutoff remain open. Review the plan before implementation; do not treat a proposed task owner or an estimated date as acquired execution authority. The user explicitly authorized source selection/copy, and that preparation is complete.

The invoked skill’s [planning guide](/Users/apaichon/.agents/skills/sdlc-agent-template/PLANNING-GUIDE.md) says: “All planning artifacts remain at `status: proposed` until a human reviews and approves them.” No approval has been inferred.

## Verification order

Bounded feature gates TEST-0006–0009 allow foundation, API, Live relay and UI fixture work to merge without waiting for later integration. Early staging uses TEST-0010; Laya qualification uses TEST-0012; integrated acceptance uses TEST-0001/0002/0003/0005/0012; final release uses TEST-0004; the following-day package uses TEST-0011. Task prerequisite graph is acyclic.

## ADK, Laya and interactive UI revision

The [reference study](../REFERENCE-STUDY.md) records source findings and the interaction contract. Required Laya work adds REQ-0006, TASK-0010 and TEST-0012. The proposed runtime now has Go, Python ADK and Laya containers in one Cloud Run revision; no model resources or package compatibility are claimed proven. Estimate: 43–69 engineering hours, with 16 October deployment unchanged and higher first-day qualification risk.

## Development assistant allocation

[MODEL-ALLOCATION.md](../MODEL-ALLOCATION.md) assigns all ten tasks: GPT builds 0001/0003/0004/0005/0008/0009 and Grok builds 0002/0006/0007/0010. Each uses the opposite model as reviewer. Task/sprint/design file ownership is aligned; estimates and proposed artifact statuses are unchanged. Grok access and exact execution versions will be recorded when the user starts the assigned sessions; no automatic external dispatch has occurred.
