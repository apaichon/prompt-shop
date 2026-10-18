---
id: ROADMAP-0003
type: roadmap
title: Migrate the Python ADK voice runtime to Go
status: in_progress
owner: pm-agent
created: 2026-10-17
updated: 2026-10-18
risk: high
risk_notes: "Native streaming, interruption, tool authorization and recovery need parity evidence before runtime cutover. SDK example support does not prove application compatibility."
horizon: "Next release after the 18 October submission; milestone order proposed, dates uncommitted"
outcome: "Monti runs its live agent orchestration and embedding intent routing in Go, preserving verified spoken directions, interactive maps and recovery while removing Python from the default embedding-mode runtime."
success_metrics: ["All frozen public/private protocol and authorization cases pass against the Go implementation", "All current Python-runtime behaviors have an explicit Go parity test or reviewed equivalent", "Thirty real native-audio turns complete the defined conversation and recovery scenarios with zero stale location updates or unauthorized tool calls", "Warm first-actionable-audio and verified-route p95 remain within 10 percent of a newly measured Python baseline under identical conditions", "Report CPU, RSS, cold start and image size for both implementations at matched concurrency", "Default Go embedding-mode launcher and deployment candidate require no Python process", "A rehearsed configuration rollback restores the pinned Python release"]
tags: [voice, adk, go, runtime-migration, performance]
related: [ROADMAP-0001, ROADMAP-0002, REQ-0002, REQ-0007, DES-0001, DES-0002, DES-0003, TASK-0022, TEST-0019, DEP-0005]
---

# Roadmap: Go ADK voice runtime

## Outcome

Move Monti's Python Google ADK runtime to Google ADK for Go. Preserve Gemini Live
native audio, tool-backed product facts and the Svelte portal's existing voice/map
contract. Port the embedding adapter and its session state alongside orchestration
so the default embedding mode can run without a Python service.

This is a proposed future migration requested by the user on 17 October 2026.
The released v0.5.0 architecture still uses Python ADK. This document does not
approve an SDK version, start implementation, change the configured Live model
or claim a performance improvement.

## Why now and baseline

Go already owns the HTTP/WebSocket gateway, authentication, catalog and routes.
Python owns the live runner, audio event processing, tool host, embedding adapter
and session cleanup. A Go agent runtime could simplify deployment and reduce
runtime overhead. Measure those benefits rather than assuming that a language
change will improve remote-model latency.

Use v0.5.0 / DEP-0005 and TEST-0019 as the behavior baseline. They include the
beef-results-without-reply noise regression, current selection authorization,
private response-ready gating and mobile route visibility. The existing 631 ms
embedding p95 and ten-turn audio sample are limited local evidence, not a matched
Python-versus-Go benchmark or a production latency qualification.

Google's [ADK Go repository](https://github.com/google/adk-go) and
[bidirectional streaming example](https://github.com/google/adk-go/blob/main/examples/bidi/README.md)
were checked on 17 October 2026. The example demonstrates WebSocket live sessions
and function tools. This supports a feasibility spike, but does not establish
parity with Monti's configured model, callbacks, audio gates or recovery behavior.
Pin a released SDK and the exact source revision during the spike. Do not depend
on an unpinned main branch or copy the sample's different model into production.

## Milestones

Targets are sequential gates, not committed delivery dates. Backend-dev-2 owns
the runtime implementation, GPT coordinates shared Go wiring, QA owns parity and
native evidence, and devops owns the deployment/rollback candidate. Use sync
mode for shared gateway, launcher and deployment files.

| Order | Milestone | Requirement mapping | Evidence of completion | Gate |
|---:|---|---|---|---|
| 1 | Prove Go ADK Live compatibility and freeze the migration contract | Preserve REQ-0002 behavior; draft a successor requirement advancing ROADMAP-0003 | Pin SDK/Go versions. Run the configured Live model with microphone PCM, output audio, transcripts and function calls. Record supported and missing callbacks, cancellation and session features. | Feasibility report, successor requirement, design and ADR reviewed before build |
| 2 | Port the private agent runtime behind the existing bridge | REQ-0002 plus the migration successor | Match setup validation, authentication, event ordering, queue bounds, deadlines, cancellation, audio pacing, session limits and cleanup. Run protocol fixtures and race tests. | No public portal or catalog contract drift |
| 3 | Port tools and embedding routing to Go | Preserve REQ-0007 and DES-0003 behavior; migration successor owns the language change | Same prototype manifest/prefix, 768 dimensions, state eligibility, cosine thresholds, strong-find rule, timeouts and safe abstention. Cover find, select, repeat, summary and general conversation. | Every tool path retains Go catalog authority and current-turn authorization |
| 4 | Verify native behavior and compare resource use | REQ-0002 targets and new parity/performance tests linked to the migration successor | Run the same scenario matrix and matched CPU/RSS/cold-start/p95 measurements for Python and Go. Reproduce the injected-noise beef case and verify audible clarification, selected shelf and highlighted route. | Thirty-turn native run, recovery checks and matched comparison pass |
| 5 | Package and release the Go runtime with rollback | Migration successor plus a new deployment record | Update launcher, images, secrets, health checks, observability and CI. Rehearse restart and rollback to the pinned Python image/configuration. | Reviewed release candidate, staged smoke and full-bundle rollback evidence |

New requirement, design, ADR, task and test IDs are allocated when those artifacts
are authored. Existing requirements do not become approved or complete through
this roadmap. Explicitly amend Python-specific `Runner.run_live` and private-host
contracts in the successor design before implementation.

## Scope boundaries

- **In scope:** Go ADK agent/session orchestration, native audio streaming,
  input/output transcript side channels, current tools, embedding routing/cache,
  private bridge authorization, session state and cleanup, error mapping,
  cancellation, pending-reply protection, recovery, packaging and observability.
- **Preserved behavior:** current candidate selection, verified aisle/shelf
  speech, summary/report state, responsive maps, microphone/speaker settings,
  Start/Stop/Interrupt, stale-turn rejection and typed recovery.
- **Out of scope:** changing the Live model or voice, replacing native audio
  with separate STT/TTS, product vector search, new languages, recipes database,
  live stock, indoor positioning or an unrelated portal redesign.
- **Architecture decision:** first prove a Go runtime behind the current private
  boundary. Merging it into the existing Fiber process is a separate decision
  based on isolation, lifecycle and resource measurements. A single binary is
  not a prerequisite for language parity.

## Verification and performance gates

1. Freeze a traceable matrix from the Python tests and native regressions. Every
   Python runtime behavior must map to Go evidence. Browser tests alone cannot
   certify the real provider path.
2. Exercise greeting, general chat, ambiguous product search, spoken and clicked
   selection, unique typed route, repeat directions, summary, product switching,
   interruption, continuous capture noise and mobile map visibility. Run separate
   quota/disconnect/timeout/Stop/restart and stale-result cases.
3. Measure at least 30 real native turns per implementation on the same device,
   network, model/voice settings, catalog and concurrency. Measure latency from
   the last voiced input sample and record setup/cold start separately. The
   proposed relative gate permits at most 10% p95 regression. Also report the
   existing absolute REQ-0002 goals of 5 seconds to actionable audio and 8 seconds
   to a verified result. A baseline that misses an absolute goal does not waive it.
4. Record application CPU, RSS, startup time and image size at matched concurrency,
   including steady state and cleanup. Compare the complete default runtime,
   not one selected process. Resource reductions are desired outcomes, with no
   percentage claimed before measurement. Preserve remote API cost accounting.
5. Require zero unauthorized tool calls, stale location updates and leaked
   credentials in the test matrix. Measure goroutine/session cleanup after
   cancellation and repeated reconnects. Keep diagnostic evidence free of keys,
   private transcripts and raw shopper recordings.

## Risks and dependencies

- Go and Python SDKs may differ in native audio events, lifecycle or tool hooks.
  Stop the cutover if the pinned Go SDK cannot provide required behavior. Record
  any proposed workaround in the design rather than bypassing ADK silently.
- Timing changes can reintroduce the pending-reply cancellation bug. Port both
  private response-ready ordering and the browser's preparation/playback hold
  contract, then rerun the retained before/after noise scenario.
- Existing Go source ownership and Python task locks still apply. Use one task
  worktree per implementation task with serialized shared wiring, and preserve
  TASK-0021's ownership and historical acceptance evidence.
- The migration needs current Live model entitlement, private provider secrets,
  matched benchmark infrastructure and a qualified deployment environment.
- Keep the Python image/configuration available through the observation and
  rollback window. New sessions can switch implementations, but an active
  native session is not transferred between runtimes. Reconnect explicitly.
- GCP topology and resource limits require new evidence. Removing Python does
  not by itself qualify fewer containers, lower allocation or production load.

## Execution start — 18 October 2026

The user authorized starting this roadmap. TASK-0023 claims milestone 1 in sync mode, with REQ-0008, DES-0004, ADR-0003 and TEST-0020. The first gate uses pinned SDK wire tests and a real-model probe. Full runtime cutover follows the capability decision; no cloud rollout is included.

### First build evidence

TASK-0023 builds Go ADK v2.6.0 with GenAI v1.74.0 in an isolated module. Real configured-model manual PCM and text probes pass only with three versioned compatibility patches: realtime configuration forwarding, modern Gemini 3 Live input handling and synchronized socket writes. Stock failures remain recorded in TEST-0020. This clears core feasibility for a reviewed patched candidate; the actual bridge/tool-host port, bounded server transport, native shopping parity, resource comparison and rollout remain later milestones. Python remains the running application.
