---
title: "Prototype operational readiness and demo runbook"
status: proposed
owner: devops-agent
created: 2026-10-13
updated: 2026-10-16
risk: critical
related: [DEP-0001, REQ-0004, REQ-0005, REQ-0006, TASK-0005, TASK-0006, TASK-0008, TASK-0009, TASK-0010, TEST-0004, TEST-0005, TEST-0012]
---

# Readiness draft

This is a planning checklist, not an incident or evidence of a running system. All boxes are pending. Deployment details and provider limits are governed by [DEP-0001](../08-deployments/DEP-0001.md) and DES-0001. The user is the project/budget owner; DevOps owns release/recovery, backend owners own database/speech fixes, QA owns acceptance evidence, and the presenter owns the final device/network rehearsal. Confirm the actual human contact for each role on 13 October.

## Manual readiness test — step by step

Run this procedure against the exact candidate revision, then repeat the normal-URL smoke after promotion. It is a test procedure, not an execution record. Record each step as **PASS**, **FAIL**, **BLOCKED** (a prerequisite is missing), or **NOT RUN**, with an evidence reference. A page loading or a green health probe alone cannot establish release readiness.

**Source baseline, updated 16 October:** the later [voice-start fix](../../VOICE-START-FIX-2026-10-16.md) connects local catalog/routes, map and the Go/ADK/Laya voice path and records one real synthetic browser lookup/route/audio check. [TEST-0012](../07-tests/TEST-0012.md) still records Laya accuracy of 19/40 against the required 36/40; complete deployment acceptance remains unverified. Recheck the exact candidate; do not infer that every checklist step passes from this local smoke.

### Step 1 — Prepare the environment and evidence sheet

1. Choose either local diagnosis or deployed acceptance. For local startup, follow [initial testing](../../INITIAL-TESTING.md): `make mvp-start` enables full dependency readiness; a separately started foundation-only server checks just the database/schema/seed. For deployed acceptance, use the approved HTTPS origin and `READINESS_MODE=full`.
2. Record the date/time/timezone, tester, environment, exact URL/origin, source commit, serving revision, all three image digests, schema/seed/map versions, ADK dependency lock/bridge version, Laya checkpoint and provider model/voice. Record secret versions only.
3. Confirm browser access through the actual reviewer access path, a working microphone/speaker, and the declared demo browser/device/network. Have a separate anonymous browser window and two maintainer sessions available.
4. Obtain the approved maintainer login through the protected channel. DevOps must identify the known good revision and compatible database before restart, outage or rollback drills. Perform those drills in the designated test environment under the release runbook.
5. Use the frozen synthetic cases in [tests/README.md](../../../tests/README.md). Keep new catalog test records separate from benchmark products. Do not change failed prompts or expected products to obtain a pass.

**Expected:** the candidate and test scope are identifiable, access works, and the required fixtures/operators are available. Missing cloud access means deployed checks are BLOCKED; local results remain local.

### Step 2 — Check the public health and readiness endpoints

From the repository root, substitute the actual origin for `https://APPROVED_HOST`. Run each command separately; no credentials belong in the URL. For local diagnosis only, use `http://localhost:8080` instead.

```sh
rtk proxy curl --silent --show-error --include --max-time 10 https://APPROVED_HOST/healthz
rtk proxy curl --silent --show-error --include --max-time 10 https://APPROVED_HOST/readyz
```

1. Check the HTTP status, content type and JSON body, not only curl's exit status. Curl can exit successfully for HTTP 503.
2. `/healthz` must return HTTP 200 and `{"status":"ok"}`. This proves the Go process responds.
3. `/readyz` must return HTTP 200 and `{"status":"ready"}`, with `X-Readiness-Scope: full` for deployed acceptance. Header names are case-insensitive. A `foundation` scope cannot pass deployed readiness.
4. If `/readyz` returns HTTP 503 and `{"status":"not_ready"}`, record the failure and inspect dependency state in step 3. A redirect or access-denied response requires resolving the approved access path; it is not application health evidence.

**Expected:** both endpoints pass on the intended revision, and responses expose no credentials or database connection details. Save only status, scope, timestamp and safe request/correlation ID. Even a full readiness pass does not prove provider access, classifier accuracy, public API registration or a working backoffice.

### Step 3 — Check database, ADK and Laya readiness

1. Have the operator verify the expected schema/seed/map versions, the reviewed seed's 60 products/eight aisles, entrance node and stored shelf mappings. Later designated test products must be accounted for separately. Verify the database is independent of application container storage.
2. From the approved private runtime context, inspect ADK `http://127.0.0.1:8001/healthz` and Laya `http://127.0.0.1:8003/healthz`. These are private checks; do not expose sidecar ports to make them browser-accessible.
3. ADK must return HTTP 200 with `status: ok`; this checks configured key/bridge secret and classifier import, not a successful provider session. Laya must return HTTP 200 with `ready: true`, `schema_version: intent-v1` and the pinned `model_revision`, after real weights load and warm up.
4. Verify startup order Laya → ADK → Go, offline bundled model loading, and locked dependency/checkpoint identities against the candidate image records. Health checks must not create provider sessions.
5. In the isolated rehearsal, stop one dependency at a time and repeat `/readyz`. It must stop reporting ready; `/healthz` may remain 200. Restore the dependency and verify full readiness recovers. Record safe failure categories and timings rather than secrets or request bodies.

**Expected:** database and sidecar checks pass, dependency loss is visible, and recovery works. Complete the actual classification/voice checks below even when all probes are green.

### Step 4 — Test typed search and shelf directions

1. Open `/` in the anonymous browser. Confirm the shopper portal requires no maintainer login and labels the map as sample data with **From entrance** as the origin.
2. Type `whole milk`, then select **Find item**. Compare the returned product (`milk-whole-1l` in the current seed), aisle and shelf with the reviewed catalog fixture.
3. Select **Show route**. Check that the route begins at the labeled entrance, ends at the selected product's stored pickup point, follows connected walkable edges and avoids shelf interiors. Compare text directions with the map.
4. Search `milk` and explicitly select a different candidate. Only the chosen product's location/route may remain selected. Search for a deliberately absent synthetic item; expect a truthful unavailable result with no invented shelf.
5. Repeat using keyboard navigation and the actual screen reader; check focus/status announcements and usable directions at desktop and mobile widths. Use [TEST-0003](../07-tests/TEST-0003.md) for the complete route/accessibility checks.

**Expected:** real API-backed products and correct walkable routes render. A 404 API, placeholder map or fixture-only response fails this integration check; record the missing route/registration as a blocker.

### Step 5 — Test the required English voice flow

1. On the approved HTTPS origin, start the voice assistant and allow microphone/playback when prompted. Confirm a WSS session establishes with the configured exact Origin and a freshly issued single-use ticket.
2. Say the frozen prompt `Where is the whole milk?` and listen to the complete reply. Confirm audible useful speech, a verified product card and a location that matches stored catalog facts. Filler speech and captions alone do not pass.
3. Ask for `milk`, then choose one of the returned candidates by voice. Confirm the selected card, spoken directions and map agree. Ask to repeat the directions; then make an out-of-scope request and verify no catalog write or unrelated action occurs.
4. Have the voice owner correlate safe counters/IDs to prove the actual native `gemini-3.8-live` session runs through ADK `Runner.run_live()`, real Laya `classify_intent`, and validated read-only catalog/route tools. Verify mono PCM16/16 kHz input and PCM/24 kHz output from configuration and safe runtime facts.
5. In the same session say `Hello`, ask `What is two plus two?`, then `Suggest a simple egg dish for dinner`. Expect complete conversational audio replies. Follow with `Where is the whole milk?`; expect catalog-backed shelf/route facts. General chat and meal ideas must not trigger fabricated store matches or be silenced by an advisory classification abstention. Ingredients are suggestions until matched through store tools.

**Expected:** the actual required model, ADK, classifier, tools, audible answer and UI work together. A model name in the UI, direct provider connection bypassing ADK, mock labels or typed-only success cannot pass. Preserve identity/counter evidence without recording audio, transcripts or tool bodies.

### Step 6 — Test interruption, permissions and reconnect

1. Interrupt a spoken answer with another item request. Obsolete playback must stop; delayed tools/cards from the earlier turn must not replace the new selection.
2. Disconnect the network during a turn, restore it and use the explicit restart control. Confirm old capture/playback/queued audio stops, resources are released, and reconnect creates a fresh ticket/session with no recorded-turn replay.
3. Deny microphone permission in a fresh browser context. Confirm a clear recovery message and usable typing. Restore permission and deliberately start a new session. Separately test playback denial/unsupported capture as described in [TEST-0002](../07-tests/TEST-0002.md).
4. Measure separate setup, idle and session-expiry cases: setup bounded by 30 seconds, idle by 60 seconds and application session by 300 seconds from ready; confirm the configured outer Cloud Run timeout is 360 seconds. Observe a visible expiry/restart state and release of provider/admission resources.

5. During a complete reply, stay quiet and leave a short pause before the next
   question. Quiet background input must not silently discard the reply. Ask a
   follow-up without restarting and verify the microphone indicator stays active.
6. In the fault harness, omit/delay the current turn's required tool result. A
   recognized request gets at most one continuation attempt after eight seconds.
   If it still cannot complete, expect “please ask again” with the session and
   microphone still active, then ask a fresh question and verify an answer. The
   expired turn's late audio/cards must be ignored. Actual provider/network failure
   still uses explicit fresh-session restart; this turn timeout does not.

**Expected:** each failure has bounded, explicit recovery with no stale results or leaked sessions. Keep these fault trials separate from normal warm timing samples.

### Step 7 — Test protected catalog maintenance

Follow [backoffice setup](../../../internal/backoffice/README.md) and [TEST-0005](../07-tests/TEST-0005.md) for the full authentication and direct-request matrix.

1. In the anonymous browser, open `/backoffice` and confirm login is required. An anonymous `GET /api/backoffice/products` must return HTTP 401 when backoffice is configured; HTTP 503 means it is unavailable and cannot pass acceptance.
2. Log in through the UI. Inspect cookie attributes without copying its value: `__Host-maintainer`, Secure, HttpOnly, SameSite=Strict, Path=/ and no Domain. Verify the server session has an absolute eight-hour expiry.
3. Create a uniquely named synthetic product with an English alias and an existing mapped shelf. Save as draft; verify it is absent from anonymous search. Publish; verify a fresh shopper search finds the committed alias, shelf and route without a frontend rebuild.
4. Edit its alias/shelf and save. Confirm it returns to draft and disappears from public lookup until republished. Archive it and verify it is absent from search and direct route/tool reads, including requests using its old ID.
5. In two maintainer sessions, load the same product version. Save in A, then attempt B's stale save. Expect HTTP 409 with a reload/review message and A's data preserved. Submit an invalid shelf/empty name through the direct-request checks; expect 422 and no partial change.
6. Exercise missing/wrong CSRF and wrong-Origin writes using TEST-0005's synthetic requests. Expect rejection and unchanged data. Log out and repeat a protected read/write; expect server rejection. Check an expired session separately without changing production clocks or shortening the release contract.

**Expected:** only a valid server session plus valid Origin/CSRF can mutate the catalog. Drafts/archived products stay private; invalid or stale writes cannot corrupt data. Archive the designated test product after testing and retain only safe operation/version evidence.

### Step 8 — Check private boundaries and secret handling

1. Execute the ticket/Origin and private-boundary negative cases in [TEST-0002](../07-tests/TEST-0002.md) and [TEST-0010](../07-tests/TEST-0010.md): missing, reused and expired tickets and wrong-Origin upgrades must fail before provider connection.
2. Verify ports 8001/8002/8003 have no public ingress and Fiber does not proxy private `/live`, `/classify` or tool callbacks. Through the private test harness, confirm wrong bridge tokens, missing/wrong Laya tokens and expired/mismatched callback capabilities are rejected.
3. Inspect served assets/config, request URLs and representative application/proxy/error logs from the synthetic run. Check that provider keys, SQL credentials, cookies, authorization headers, audio, transcripts and classification input text are absent. Do not export HAR files, credential-bearing screenshots or request-body traces.
4. Confirm closing/error/cancellation clears transient session data and releases browser, bridge, provider and worker resources. Verify browser and Go receive no Gemini key; SQL credentials remain in Go.

**Expected:** denied probes produce no provider session or data mutation; no secret/content leakage is observed. Record safe verdicts and correlation IDs, never the sensitive values inspected.

### Step 9 — Verify actual Laya accuracy and bounds

1. Execute [TEST-0012](../07-tests/TEST-0012.md) through the actual ADK classifier harness using the pinned real checkpoint and all 40 frozen English inputs. Record expected/actual labels by fixture ID, confusion matrix, coverage and model/build identity.
2. Require at least **36/40** correct; abstentions/errors count as misses. Preserve the frozen confidence ≥0.70 and top-two margin ≥0.15. An unchanged 19/40 result fails; do not disable Laya or tune against the same holdout to mark a pass.
3. Separately test one active inference/four queued, queue wait ≤200 ms, total deadline ≤1,200 ms, overflow/timeout abstention, no retry and stuck-worker cleanup. Missing credentials, model-load failure and cancellation must return safe bounded failures.
4. Measure cold load and 30 warm classifications separately, including queue time; record actual deployment CPU/RSS/startup peak. A host result or image build alone cannot qualify the deployment resource limits.

**Expected:** actual inference passes accuracy, contract, resource and failure bounds. Warm classifier p95 must fit ≤1,200 ms. Missing measurements or a failed accuracy gate blocks release even if voice occasionally succeeds.

### Step 10 — Measure warm performance and concurrent use

1. Warm the candidate and run the 30 frozen normal English voice cases. On one client monotonic clock measure last voiced microphone sample → first actionable audible reply and → first verified card render. Audit the complete spoken answer against tool facts.
2. Run 30 typed queries measured from submit → visible candidates, then 30 selections measured from confirmation → visible route. Follow [tests/README.md](../../../tests/README.md) for the observation fields and fixture IDs; HTTP duration alone is insufficient.
3. Preserve every trial and failure. For each 30-sample series, sort the durations ascending; nearest-rank p95 is sample **29**. Targets: actionable speech ≤5 seconds, grounded card ≤8 seconds, typed lookup ≤2 seconds and selection-to-route ≤2 seconds. Missing/failed normal trials cannot be dropped to claim a pass.
4. Run five simultaneous Live users plus typed/admin requests as a separate load trial. Observe per-instance admission, aggregate SQL pools, provider quota, queue bounds and CPU/RSS. With the proposed four-session per-instance cap, verify the approved deployment's instance distribution admits all five; rejection or unavailable capacity cannot be counted as a five-user pass.
5. Close all sessions and confirm active provider connections, admission slots and queued work return to their prior baseline. Record cold start/setup separately from warm and load trials.

**Expected:** all required correctness and performance gates pass on the same candidate, and overload/close recovery is bounded. Keep raw timing samples and actual runtime limits with the evidence.

### Step 11 — Prove persistence and rehearse rollback

1. Before the supervised app restart/revision replacement, record schema/seed/map/catalog versions, reviewed row counts/checksum and the designated test product ID/state. Preserve PostgreSQL; do not rerun a destructive fixture reset or delete its volume.
2. Replace/restart the application revision, verify full readiness, and repeat lookup/backoffice read. The same committed records must remain. A second app using the same live DB does not prove DB-container durability; verify the independent durable database/storage configuration separately.
3. Follow [the release/rollback operator guide](../../../deploy/RELEASE.md) with DevOps. Observe a controlled failure on the isolated test revision, start the recovery timer at rollback initiation, and restore the qualified matched Go/ADK/Laya image/configuration set with compatible schema and secret versions.
4. Verify old sockets close/drain with a restart notice. Start a fresh session and repeat steps 2, 4, 5 and the protected backoffice smoke on the restored revision. Stop the timer only after the real flow is restored; require **≤15 minutes**.
5. After the approved final promotion, repeat those smokes at the normal reviewer URL and verify the final intended revision/image/model identities. A successful traffic command alone does not pass. Complete the guide's final state capture after the last smoke.

**Expected:** data persists, rollback restores the complete flow within target, and final normal-URL evidence identifies the intended release. If there is no qualified baseline or compatible recovery path, mark rollback BLOCKED.

### Step 12 — Record the readiness decision and close sessions

1. Confirm [TEST-0001](../07-tests/TEST-0001.md), [TEST-0002](../07-tests/TEST-0002.md), [TEST-0003](../07-tests/TEST-0003.md), [TEST-0005](../07-tests/TEST-0005.md) and [TEST-0012](../07-tests/TEST-0012.md) have applicable evidence for this source/revision, plus [TEST-0010](../07-tests/TEST-0010.md) for early staging and [TEST-0004](../07-tests/TEST-0004.md) for final release. Rerun affected gates after changes.
2. Use the record below for each step. Preserve failures, owner actions and evidence references; use only synthetic fixtures and redacted artifacts. Check boxes in the dated checklist only when supported by actual observations.
3. Any required FAIL, BLOCKED or NOT RUN means **NOT READY**. All required passes make the candidate ready for DevOps/QA and owner review; this procedure does not deploy, approve or submit automatically. The separate 17 October rehearsal/package gate remains [TEST-0011](../07-tests/TEST-0011.md).
4. Close all shopper/maintainer windows, log out and verify provider/bridge sessions have ended. Hand unresolved blockers to the named owner and record the next check; do not leave cloud cleanup to an assumed date.

Copy this blank record into the run's controlled evidence bundle; it does not set test-artifact statuses or `last_run`:

```text
Run date/time/timezone:
Tester / reviewer:
Environment / origin / source commit / serving revision:
Go / ADK / Laya image digests:
Schema / seed / map / checkpoint / dependency-lock identities:
Browser / device / microphone / network:
Step and case ID:
Expected result:
Observed result and safe timing/correlation ID:
Verdict: PASS | FAIL | BLOCKED | NOT RUN
Redacted evidence reference:
Blocker owner / next action:
Overall decision: NOT READY | READY FOR OWNER REVIEW
DevOps / QA review and time:
```

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
