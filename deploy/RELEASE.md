# TASK-0008 release and rollback operator guide

`release.py` qualifies existing Cloud Run revisions, records a named traffic change and checks final owner-reviewed evidence. Run with Python 3.11+ from the Task 8 worktree. It builds on Task 5's staging/image contracts and recomputes Task 6 QA; it does not provision resources or create a substitute model/classifier image.

Current source is annotated `v0.1.0`, main `50054b23cfe3336d019fee8da0db474da27940e0`. Its [source audit](evidence/TASK-0008/source-audit.json) is **blocked**: actual routing and Laya build inputs are missing; gcloud/configuration and deployed candidate/baseline/QA evidence are unavailable. The previously merged/tagged source is not an accepted deployed release. Never move that tag after fixing modules; qualify and tag a new version through GitFlow.

## Local preparation and checks

Ignored mode-0600 templates were created at `deploy/local/staging.json`, `images.json`, `release.json`. The tracked `.example.json` files can recreate them in another checkout. Fill real approved metadata and pinned secret **names/versions**, never keys, passwords, bearer cookies, API tokens, raw audio or shopper transcripts. Runtime secrets stay in the Task 5 Secret Manager flow. Actual credentials do not belong in a release JSON or artifact.

```sh
rtk proxy python3 -m unittest discover -s deploy/tests -v
rtk proxy python3 deploy/release.py audit --tag v0.1.0 --config deploy/local/staging.json --out deploy/out/source-audit.json
```

Tests use synthetic SDK/QA fixtures and temporary Git repositories; they prove controller rejection and state handling, not cloud/native-model acceptance. Audit exits 1 for release blockers; malformed/incomplete command inputs exit 2 with a fixed error label. It never calls the cloud. Actual Cloud Run release execution is not available until Task 5 staging and Task 6 acceptance are complete.

## Freeze the release inputs

Follow [Task 5's build/provisioning runbook](README.md). Provide an authorized GCP project/number/region, exact service/registry/SQL identity, budget/access/retention and scoped operator identity. Build all three runtime images from the same reviewed committed source and resolve actual registry digests. Verify actual Laya weights/config/tokenizer/license and runtime startup, then run migration/import once with the operator identity. Qualify the candidate at zero ordinary traffic alongside a complete, previously accepted rollback revision. First staging has no known-good baseline and cannot claim rollback rehearsal.

`release.json` accepts exactly the `release.example.json` fields. Set the actual annotated `git_tag`, matching 40-hex `source_commit`, explicit `candidate_revision` and recorded release `approved_by`. `known_good` records its own revision/source commit, all three immutable regional registry image digests, complete separately pinned secret-role inventory and actual Laya model revision. `staging.json.previous_revision` must name that baseline. Keep source/build/checkpoint/secret/schema compatibility provenance with the release; a name alone is not a known-good revision.

Candidate browser testing must use exactly the configured `PUBLIC_ORIGIN`. A candidate tag URL is another origin, and changing origin/env after testing creates a different revision. Arrange and qualify the approved same-origin reviewer access path before collecting QA; do not bypass Origin/cookies, silently add origins or count a UI model label as provider identity. The controller requires the same-origin artifact plus native QA on that origin/revision. See [Cloud Run traffic tags and rollout guidance](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration).

Copy actual Task 6 observations, HTTP results and their redacted reviewed artifacts into an ignored evidence directory (for example `deploy/local/evidence`). Names are selected by `qa_observations`, `qa_http_run`, `qa_artifacts` in release.json. The controller recomputes the frozen 30/40-query gates; an old `BLOCK_RELEASE`, different source/revision/origin or unqualified real model/checkpoint cannot promote. HTTP request time or a traffic-command exit code cannot stand in for audible/rendered latency.

## Reviewed check artifacts

Each of the eleven `checks` entries requires `status: pass`, a reviewer, a single local `.json` artifact filename and its SHA-256. The artifact is at most 2 MB, a regular non-symlink file and has this common envelope:

```json
{
  "schema_version": "release-check-v1",
  "environment": "deployed",
  "subject": {
    "project_id": "REAL_PROJECT", "region": "REAL_REGION", "service": "REAL_SERVICE",
    "candidate_revision": "REAL_CANDIDATE", "source_commit": "FULL_COMMIT",
    "known_good_revision": "REAL_BASELINE", "origin": "https://REAL_HOST"
  },
  "check": "CHECK_NAME", "verdict": "pass", "reviewer": "ACCOUNTABLE_REVIEWER",
  "observed_at": "UTC_ISO_TIMESTAMP", "facts": {}
}
```

Use real redacted observations and owner review, not the example placeholders. Required facts:

| Check | Facts and required owner inspection |
|---|---|
| `build_provenance` | `verified: true`; actual source/OCI image labels, all three build/digest records, package/model asset hashes/license, no fixture entrypoint, image contents/privacy/security qualification |
| `baseline_qualification` | `bundle` exactly equals `known_good`, `native_voice_and_backoffice_verified: true`; previous accepted native ADK/Gemini/Laya and protected backoffice evidence |
| `schema_compatibility` | `additive_only: true`, `rollback_database_writes: false`, nonempty actual `current_schema_version` and `baseline_schema_version`; review both readers against the current durable database, backup/recovery path and no destructive schema/data reversal |
| `same_origin_access` | exact `verified_browser_origin`, `candidate_revision`, `actual_native_session_verified: true`; actual access/TLS/cookie/WSS path through the approved origin |
| `secret_versions_available` | `verified: true`; current enabled compatible numeric secret versions, scoped IAM and all matched Go/ADK/Laya bindings, including baseline versions; never fetch/save their values |
| `candidate_native_smoke` | `verified: true`; full TEST-0004 step 1–3 on candidate, actual required model/ADK/PCM/classifier/tool/audio/card/route, selected-item correction and bounded recovery |
| `persistence` | `verified: true`; catalog/map/schema/seed checksum/count and designated non-holdout imported ID before/after actual revision replacement, post-restart lookup and shared backoffice/public consistency |
| `privacy` | `verified: true`; served assets and controlled representative logs, no credentials/raw audio/transcripts, authenticated private callbacks, cleanup/interruption/epoch checks |
| `five_user_load` | integer `simultaneous_live_sessions >= 5`, `typed_and_admin_requests_observed: true`, `bounds_and_recovery_verified: true`; separate load/resource/provider/pool evidence, never mixed with normal warm latency |
| `monitoring_owner` | `verified: true`; named responsible operator, approved budget alerts, observed monitoring and feature-freeze/change-freeze/high-risk release review; one operator during mutations |
| `optional_languages` | `offered` array limited to th-TH/zh-CN/ja-JP and `all_offered_smoke_passed: true`; empty offered array is valid for English-only. Disable or fix failing offered locales |

Booleans/hash matching qualify reviewed artifacts; they are not independent proof that the facts happened. Keep the underlying redacted measurements/captures and reviewer decision auditable. Follow [TEST-0004](../docs/sdlc/07-tests/TEST-0004.md) plus its linked Task 6 suites for actual procedures.

## Capture, plan and promote

Install/authenticate the approved Google Cloud SDK when setup is available. Its read-only capture checks namespace, location, runtime identity, readiness, exact three digests/secret pins, limits, startup/probe/private-port behavior, concrete traffic percentages and IAM. It stores only validated contract fields and omits arbitrary metadata, raw SDK stderr and principal emails. Capture before each operation; snapshots older than five minutes are rejected.

```sh
rtk proxy python3 deploy/release.py capture --config deploy/local/staging.json --images deploy/local/images.json --release deploy/local/release.json --operation promote --out deploy/out/pre-promote.json
rtk proxy python3 deploy/release.py plan --config deploy/local/staging.json --images deploy/local/images.json --release deploy/local/release.json --operation promote --captures deploy/out/pre-promote.json --evidence deploy/local/evidence --out deploy/out/promote-plan.json
```

Plans are offline and display the exact operation in JSON. Only the following explicit command changes existing traffic:

```sh
rtk proxy python3 deploy/release.py execute --config deploy/local/staging.json --images deploy/local/images.json --release deploy/local/release.json --operation promote --captures deploy/out/pre-promote.json --evidence deploy/local/evidence --plan deploy/out/promote-plan.json --execute --out deploy/out/promote-receipt.json
```

Execution recomputes all gates/hashes, re-reads live service/revisions/IAM and rejects drift before mutation. It writes intent first, invokes the fixed named-revision 100% command once and re-reads effective traffic/bundle. No `LATEST`, IAM mutation, provision, migration, credential read, SQL reversal or automatic retry is performed. Use a new output path each time; never overwrite operation history. Cloud SDK permission/transport/result failures keep `CHANGE_ATTEMPTED_RESULT_UNVERIFIED`; the service may have changed despite an ambiguous command result. Inspect live state with the accountable operator and create a fresh capture/plan before further action.

Successful traffic verification records `TRAFFIC_VERIFIED_SMOKE_PENDING`. Immediately complete the actual normal-origin native/backoffice smoke, including fresh-session target and graceful restart of old sockets; command success does not pass the release. Traffic changes are not instantaneous, and existing sockets can remain on the old revision. An exclusive operator/change freeze is required: read-and-check drift protection is not an atomic Cloud Run compare-and-swap transaction. See [the official update-traffic command](https://docs.cloud.google.com/sdk/gcloud/reference/run/services/update-traffic).

## Rollback rehearsal and final promotion

After a passed post-promotion normal-origin smoke, rehearse the supervised isolated failing revision from TEST-0004. Route only approved test traffic to it, observe the controlled failure, and preserve the ordinary database. Capture/plan/execute rollback with `--operation rollback` and new output filenames; the ordinary traffic context remains the candidate while isolated fault test traffic uses the qualified access path. The named target is the previously qualified full baseline revision, including its image/secret pins. A failed candidate or failed new QA does not block recovery; baseline qualification, current DB compatibility, secret availability, responsible owner and unchanged current traffic context are still required. Rollback never pretends to reverse DB writes or automatically reverts the immutable Git tag.

Time recovery from the rollback receipt's `started_at` through completion of the real restored native/backoffice smoke. The complete interval must be <=900 seconds; `traffic_operation_ms` measures only command/verification and cannot satisfy the recovery target alone. Preserve failed/outage cases separately.

Capture the isolated fault revision identity without storing its arbitrary env/metadata:

```sh
rtk proxy python3 deploy/release.py fault-capture --config deploy/local/staging.json --images deploy/local/images.json --release deploy/local/release.json --failing-revision REAL_ISOLATED_REVISION --out deploy/local/evidence/fault-revision.json
```

The `fault_injection` proof uses the same four-field status/reviewer/artifact/sha256 index. Its artifact envelope has `check: rollback_fault_injection`; `subject` is the release-check subject plus `operation_sha256` of the rollback receipt. Facts include distinct same-service `failing_revision`, `failure_observed: true`, `test_traffic_isolated: true`, `ordinary_database_preserved: true`, `revision_capture` (the single fault-capture JSON filename) and its raw-file `revision_capture_sha256`. Capture and failure-observation timestamps must fall between the initial normal-origin smoke and rollback initiation. Actual supervised failure observation remains an owner-reviewed artifact; a Ready flag alone cannot establish runtime failure. The controller does not create or mutate the deliberately failing revision.

Then capture/plan/execute promotion again after full candidate gates, returning final normal traffic to the accepted candidate. Perform the full final normal-origin smoke. Keep all three operation receipts and all three smoke artifacts plus the isolated fault/capture proof.

Smoke artifacts use the envelope above with `check: native_release_smoke`; their `subject` instead contains exact project/region/service, target `revision`, target `source_commit`, origin and `operation_sha256` (SHA-256 of canonical sorted compact JSON of that operation receipt, as computed by `release_contracts.digest`). Facts must include exact `images`, `model_revision`, and all ten booleans:

`https_ready`, `native_gemini_3_8_adk`, `real_laya`, `audible_grounded_answer`, `verified_card_and_route`, `spoken_selection`, `protected_backoffice`, `fresh_session_on_target`, `old_socket_restart`, `no_secret_or_content_logs`.

Create a smokes index with exactly `post_promotion`, `fault_injection`, `rollback`, `final_promotion`, each holding the same four-field status/reviewer/artifact/sha256 proof used for checks. Each observed_at is UTC completion after its traffic verification and before the next operation. Rollback smoke binds the baseline's own source/images/model, not the candidate bundle.

```sh
rtk proxy python3 deploy/release.py capture --config deploy/local/staging.json --images deploy/local/images.json --release deploy/local/release.json --operation verify --out deploy/out/final-state.json
rtk proxy python3 deploy/release.py finalize --config deploy/local/staging.json --images deploy/local/images.json --release deploy/local/release.json --captures deploy/out/final-state.json --evidence deploy/local/evidence --operations deploy/out/promote-receipt.json deploy/out/rollback-receipt.json deploy/out/final-promote-receipt.json --smokes deploy/local/evidence/smokes.json --out deploy/out/release-result.json
```

The final `capture --operation verify` checks the currently candidate-serving state and retains its validated revision; it is read-only and changes no traffic. Finalization verifies actual receipt chronology/context, qualified current QA/checks, operation-bound native smokes, <=15-minute recovery, current final candidate traffic/images/IAM and unchanged source tag. It returns `ELIGIBLE_FOR_OWNER_DEPLOYMENT_RECORD`. Record actual TEST-0004/DEP-0001 evidence and owner approval via deploy-runner/task-progress-update; only then can the real deployment/task reach done. Tooling fixtures or a preflight result cannot stamp `deployed_in`.

Primary references: [Cloud Run v1 schema](https://docs.cloud.google.com/run/docs/reference/yaml/v1), [revision describe](https://docs.cloud.google.com/sdk/gcloud/reference/run/revisions/describe), [traffic rollout/rollback](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration). The SDK path is implemented/tested with offline contract fixtures but has not yet been executed against a real account in this task.
