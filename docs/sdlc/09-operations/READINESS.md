---
title: "Prototype operational readiness and demo runbook"
status: proposed
owner: devops-agent
created: 2026-10-13
updated: 2026-10-13
risk: critical
related: [DEP-0001, REQ-0004, REQ-0005, REQ-0006, TASK-0005, TASK-0006, TASK-0008, TASK-0009, TASK-0010, TEST-0004, TEST-0005, TEST-0012]
---

# Readiness draft

This is a planning checklist, not an incident or evidence of a running system. All boxes are pending. Deployment details and provider limits are governed by [DEP-0001](../08-deployments/DEP-0001.md) and DES-0001. The user is the project/budget owner; DevOps owns release/recovery, backend owners own database/speech fixes, QA owns acceptance evidence, and the presenter owns the final device/network rehearsal. Confirm the actual human contact for each role on 13 October.

## Before cloud work — 13 October

- [ ] Record project ID, billing approval, region, spend budget, alert recipient and resource-retention date.
- [ ] Verify deployer, build, runtime and migration identities; API enablement and organization-policy constraints.
- [ ] Prove actual `gemini-3.8-live` Developer API setup, browser PCM16 mono/16 kHz input, PCM/24 kHz spoken output and a validated read-only catalog/route tool call. Record model, endpoint, voice and actual account concurrency/token quotas; never treat model documentation or a Gemini 2.5 source demo as account-access proof.
- [ ] Put the Gemini Developer API key in Secret Manager and inject it only into Python ADK; neither Go nor browser bundles/frames receive it. SQL credentials remain in Go. Do not substitute Vertex/ADC credentials without a separately verified provider contract.
- [ ] Freeze and lock Python/ADK/GenAI dependency versions after a real ADK-mediated Gemini 3.8 audio/tool proof; a direct Gemini connection that bypasses ADK does not pass.
- [ ] Freeze the required English Laya checkpoint commit/weight digest, CPU dependency lock, fixed intent schema and source/model license notices; prove offline model load and real inference before approving build assumptions. Laya remains mandatory if risks materialize.
- [ ] Approve provisional total 4 vCPU/5 GiB per instance and regional quota/budget for Go+ADK+Laya; qualify actual memory, CPU latency and model startup instead of assuming these values suffice.
- [ ] Review the reused relay/shopping UI coupling and replace old model/configuration assumptions; no silent fallback to an earlier model or a separate recognition/synthesis pipeline.
- [ ] Freeze controlled-reviewer versus public access; prove browser login/access without exposing provider credentials.
- [ ] Record named presenter, reviewer access requirements, demo device/browser, microphone and network.

## Early cloud smoke — 14 October

- [ ] Go ingress serves the SvelteKit customer/backoffice portal and Fiber on HTTPS; private Python ADK and Laya containers share the revision. Verify sole ingress Go port 8080, ADK 8001, private Go callback 8002 and Laya 8003 with no public routes to sidecars.
- [ ] Independent PostgreSQL holds 60 products and eight aisles; seed rerun produces no duplicates or partial invalid imports.
- [ ] Fresh-browser microphone capture and playback work over HTTPS/WSS; denied permission, unavailable AudioWorklet or playback permission lead to clear recovery/typing.
- [ ] Ticket issuance, atomic single-use consume and exact Origin checks guard `/ws/voice`; missing/reused/expired tickets and cross-origin upgrades fail before provider connection.
- [ ] Startup order is model-warmed Laya → ADK import/config readiness → Go. ADK probe does not call Go, Laya or provider. `/live` rejects wrong bridge tokens; tool callbacks reject expired/mismatched capabilities; `/classify` rejects missing/wrong internal token; no private listener is reachable through Fiber routing.
- [ ] A native English voice turn calls a validated read-only tool, returns a real shelf/walkable route from the labeled entrance and speaks a grounded result. Interruption stops obsolete playback and prevents stale card/tool updates.
- [ ] That normal voice flow uses real Laya classification, not a mock or Gemini-only bypass. Laya accepts 1–300 characters/fixed schema, one active inference and queue four; verify queue wait ≤200 ms and total deadline 1,200 ms, timeout abstention, no retry and stuck-worker cleanup.
- [ ] Cloud Run timeout 360 seconds, app lifetime 300 seconds, setup 30 seconds and idle 60 seconds are tested; disconnect/reconnect creates a fresh session without replaying recorded audio.
- [ ] Session/frame/buffer limits, active-session slots, provider quotas, runtime memory, aggregate SQL pool size and five-user demo concurrency are observed. Socket close releases the provider connection and admission slot.
- [ ] Record CPU/RSS/startup peak for each container under load; do not reuse the old single-process 512 MiB assumption. Test sidecar loss, queue close, blocked callback cancellation and simultaneous SIGTERM drain below ten seconds.
- [ ] A known good revision, matched image digests, ADK lock/bridge version and compatible schema/secret versions are recorded for rollback.
- [ ] Laya weights/tokenizer are bundled at build with pinned digest; startup needs no model download. Record Laya lock/checkpoint provenance/license and verify CPU-only packaging independently of ADK.
- [ ] Prepare the maintainer secret and scoped database-principal configuration for TASK-0009; working login/catalog-write verification is the 15 October integration gate, not required for this early customer-only smoke.

## Observability contract

Emit structured application events containing timestamp, random request/session correlation ID, route template, error/close category, elapsed milliseconds, session setup/first-actionable-speech/grounded-card timings, active Live session count, model ID, revision and schema/seed version. Count tool validation failures, quota rejections, interruption/reconnect events, ticket/Origin rejection, queue overflow, 5xx and SQL pool waits. Measure provider usage/cost counters when available without logging content. Admin audit metadata records actor role, operation, product ID, timestamp and outcome without passwords or session contents. Log neither raw audio nor transcripts, free-text queries, WebSocket frame bodies, tool arguments/results containing user content, cookies, authorization headers, provider keys or shopper identifiers. Keep credentials out of URLs and inspect relay/framework/tracing middleware for body capture. Retain only synthetic QA fixtures; shopper audio/transcripts are transient session data and are discarded on close. Verify Developer API data-handling settings before real shopper use.

Track Laya startup/warmup duration, pinned checkpoint identity, classification count, queue/inference latency, timeout/abstention/overflow count, worker replacement and per-container CPU/RSS. Do not log classification input text. Propose a 5-minute alert for repeated readiness failures, at least 5 server errors above 10%, or at least 5 Live setup/turn failures above 20%; review low-count dashboards manually. Alert on sidecar failures, leaked sessions, queue overflow and provider rejection. Notify DevOps/presenter. Go health can remain green with unavailable voice/classification: `/readyz` and UI expose nonsecret ADK configuration and Laya model-loaded state. ADK's own probe is independent; Laya's probe requires warmed weights. Neither claims successful provider interaction or measured classifier accuracy. Use synthetic replay and correlation IDs, not transcript logs, for investigation.

## Final release evidence — 16 October

- [ ] Admin bcrypt password hash is configured through Secret Manager; opaque session hashes persist in SQL with eight-hour expiry; catalog writes are server-authenticated, CSRF-protected and absent from customer-query principal permissions.

- [ ] TEST-0004 and linked core suites pass; attach English accuracy and 30 warm-turn p95 from utterance end to first actionable speech ≤5 seconds and grounded card ≤8 seconds; typed search/route p95 ≤2 seconds. Record setup/cold-start separately; filler audio is not actionable speech.
- [ ] Actual HTTPS URL, access instructions, commit/tag, every container image digest/dependency lock, bridge version, serving revision and deployment time are recorded.
- [ ] Database survives restart/revision replacement; runtime has no migration privilege.
- [ ] TEST-0005 proves protected catalog create/update, aliases and shelf assignment; customer lookup reflects committed published products and excludes drafts/archived products; invalid references are rejected; logout/expiry and CSRF/unauthenticated-write rejection pass.
- [ ] Browser assets, request URLs, application logs and error traces contain no secret, raw audio or transcript.
- [ ] Previous revision restores service within the measured 15-minute recovery target; schema stays compatible.
- [ ] Selected access restrictions and request/scaling limits apply to candidate URLs as well as the normal service URL.
- [ ] Revision switch/rollback closes or drains old sockets and a fresh session proves the intended revision/model. No session/model fallback or recorded-turn replay occurs.
- [ ] Restore the complete matched container/configuration set during rollback; do not mix an old Go bridge with an incompatible new ADK image.
- [ ] TEST-0012 proves required Laya intent classification, ≥36/40 frozen English intent cases, model-loaded startup, overload/timeouts, internal authentication, memory and full-flow latency. Failed classifier acceptance blocks release; it is not silently cut.
- [ ] DevOps and QA accept the final normal-URL smoke by proposed **17:00 Bangkok** cutoff. Unmet gates are reported as unmet, not waived silently.

## Operator actions during rehearsal/demo

| Symptom | Immediate action | Follow-up / owner |
|---|---|---|
| Microphone/playback blocked or capture unsupported | Explain permission/playback gesture; offer typing; retry once permission changes | Presenter verifies supported browser/AudioWorklet; frontend owner investigates |
| Live setup/model/quota failure | Keep visible catalog/map results; refuse new voice sessions if needed; close failed sockets; offer explicit fresh-session retry/typing | Backend voice owner checks exact 3.8 model/config/key/quota; no older-model fallback; typing alone does not pass required voice acceptance |
| ADK crash/startup/bridge failure | Mark voice unavailable; reject new voice admission; close orphan bridge/provider work and preserve typed lookup where possible | Voice owner checks per-container health/resource limits, locked dependencies and shared bridge-secret version; never silently bypass ADK |
| Laya model load/OOM/inference failure | Surface classifier degradation; bound timeout to abstention, stop stuck worker and clear queue; refuse to claim required flow success | Laya owner checks pinned checkpoint, offline files, CPU/RSS and token; normal release requires actual classification, no silent feature removal |
| Socket interruption/network loss/session expiry | Stop capture/playback, discard queued audio, release provider/slot resources; explain fresh-session reconnect | Backend/frontend owners inspect close reason, Origin/ticket limits and queue bounds; never replay a recorded turn automatically |
| Wrong item or shelf | Stop using that fixture; do not invent a correction in speech | Catalog owner validates source, import/version and alias; QA reruns affected and frozen prompts |
| Database unavailable | Show service-unavailable state, retain no fabricated result; check SQL instance, connection identity/pool and secret version | DevOps + backend investigate; app rollback only if regression is revision-specific |
| New revision breaks core flow | Restore known good matched image/configuration set, drain old Live sessions, then verify readiness and fresh ADK English/typed route smoke | DevOps records elapsed recovery and opens actual event record; backend supplies reviewed hotfix |
| Unexpected active sessions or spend | Restrict demo access, stop session admission and close active provider/browser sockets; reduce approved quotas where appropriate | DevOps informs budget owner; active sockets incur runtime/model usage, alerts are not caps, and SQL/storage can continue charging |
| Suspected secret exposure | Restrict access, rotate affected credential/secret, deploy the corrected revision | DevOps examines scope without copying secrets into tickets/logs; record actual incident only then |

## Rehearsal and submission — 17–18 October

On 17 October, rehearse the actual device: ADK/Gemini 3.8 voice with real Laya intent inference finding a known item; interactive shopping card selection for ambiguity; truthful unavailable-item recovery; interruption/reconnect; and protected edit-and-publish becoming visible to lookup. Verify reviewer access, logout, microphone/playback, sample-data label and “From entrance” origin. Run a cold start including Laya model preload, then warm turns; keep three-container warming/session costs explicit. Close browser, bridge and provider sessions at the end.

Prepare a short walkthrough, screenshots, a backup recording clearly labeled as recorded, a setup/runbook, source/release reference and a checklist of supported versus stretch features. Extra languages or recipes may be shown only if separately verified; the required English release must remain intact. User reviews the submission package before submission on 18 October; this plan does not submit anything automatically.

After submission, retain or remove cloud resources on the owner's agreed date. Turning off Cloud Run traffic does not remove SQL, artifact or log storage charges. Export the sample dataset and release evidence before any approved cleanup; record the actual cleanup as an operations event only when it occurs.

## Questions for review

1. Which GCP project, billing account, budget and region are approved, and who can grant required IAM access?
2. Should reviewers use controlled browser access or an explicitly public demo, and when should external access end?
3. Which presenter/device/network and Gemini Developer API account/key/voice/quota are approved after proving the required `gemini-3.8-live` path?
4. Is 16 October 17:00 Bangkok the accepted deployment cutoff, and who is the release/recovery contact?

## Dated verification gates

Early 14 October cloud staging uses TEST-0010 with ADK/Gemini audio/tools and real Laya classification. Integrated acceptance on 15 October uses TEST-0001/0002/0003/0005 and required TEST-0012. Final 16 October promotion adds TEST-0004 release/rollback evidence. The 17 October package is TEST-0011 and does not block the 16 October deployment. See TASK-0005, TASK-0006, TASK-0008 and TASK-0007 respectively.
