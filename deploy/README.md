# TASK-0005 staging preparation

This directory prepares **one three-container Cloud Run revision plus durable Cloud SQL**. It does not represent an executed deployment. No project, budget, region, reviewer access, SQL tier, model access or cleanup date has been approved in this build session. No runtime image digest, staging URL or live voice result is claimed.

Use Python 3.11+, Docker with Linux amd64 builds, authenticated Google Cloud CLI, and `rtk` locally. CI runs only offline tests and needs no cloud credentials. No workflow deploys automatically or stores service-account JSON keys.

## Files and validation

- `staging.py`: validates configuration, prints first-provisioning commands, or renders Cloud Run service/import-job JSON (valid YAML). It never invokes Google Cloud.
- `build.py`: creates an allowlisted context from **one committed integration tree**, verifies the English model bundle, prints or runs local Docker builds. It never pushes images. Uncommitted files and local env files cannot enter its context.
- Root, `agent/`, `intent/` Dockerfiles: nonroot Go/static portal, ADK and offline Laya images. All five base references must be immutable digests. Example pins were resolved from upstream registries on 2026-10-14; they still require vulnerability and target-platform qualification before staging.
- `verify_model.py`: matches the pinned checkpoint/license/files to SHA256 checksums. This is integrity verification, not inference evidence.
- `tests/`: deployment-contract, isolation, negative-input and committed-context tests, all offline.

```sh
rtk proxy python3 -m unittest discover -s deploy/tests -v
rtk proxy python3 deploy/check_docker_context.py
rtk proxy mkdir -p deploy/local
rtk proxy cp deploy/staging.example.json deploy/local/staging.json
rtk proxy cp deploy/images.example.json deploy/local/images.json
```

Fill local JSON with configuration and **secret names/versions only**. Never put secret values there. Null fields intentionally fail validation. `approved_by` records the actual cloud authorization; filling a field does not obtain authorization. The spending amount includes its billing currency, e.g. `25USD`. Supply a verified email Monitoring notification-channel resource name, the billing account and project number, and a cleanup/retention date. Budget notifications at 50/80/100% are alerts, not a hard cap. SQL disk growth is bounded and must be monitored; min0/max2 applies per revision, so overlapping revisions can exceed two instances in total.

The region suggestion is `asia-southeast1`; retain it only if approved. SQL is PostgreSQL 16 Enterprise, zonal, approved tier/storage, connector-enforced public IP **without authorized networks**, daily backups, PITR and deletion protection. Organization policy requiring private IP/VPC needs a reviewed change before applying this plan. This task does not silently choose the database's cost.

## Integration handoff (required before production builds)

`origin/develop` was planning-only at c57cd6f when this work began. Foundation is draft PR #1 at a564571; ADK/voice is draft PR #2 at d973879. Both remain separate inputs, not a qualified integrated source commit. Respect each builder's exclusive files. Rebase this task after approved integration; do not copy an uncommitted feature tree into production images.

| Owner | Required input/behavior |
|---|---|
| TASK-0001/shared wiring | `cmd/server`, `cmd/import`, module lock and migrations; full readiness; static files from `STATIC_DIR=/app/web/build`, SPA fallback excluding APIs; server binds `$PORT`; SIGTERM drains in <10s |
| TASK-0002/shared wiring | Register real catalog/route handlers and the TASK-0003 catalog adapter; fixed readonly/backoffice/ticket pool limits 2/2/1; keep private tool server bound only to 127.0.0.1:8002 |
| TASK-0003/shared wiring | Register voice gateway, exact `PUBLIC_ORIGIN`, `VOICE_ENABLED=true`, `ADK_BRIDGE_SECRET`; use `TICKET_DATABASE_URL` for the one-connection ticket pool; actual setup30/session300/idle60 and four-session cap; fresh reconnect |
| TASK-0004 | `web/package.json`, npm lock, `npm run check`, static `npm run build` producing `web/build/index.html` and assets; no secret-backed frontend build variables |
| TASK-0009/shared wiring | `BACKOFFICE_DATABASE_URL` and `ADMIN_PASSWORD_HASH` are proposed deployment handoff names, not currently implemented configuration; keep backoffice protected and credentials separate |
| TASK-0010 | `intent/pyproject.toml`, `uv.lock`, CPU dependencies, `intent_service.app:app`; `LAYA_MODEL_PATH`, `LAYA_INTERNAL_TOKEN`; port8003 `/healthz` after real model warm-up; one worker with bounded inference subprocess/queue and cleanup; `agent/tools/intent.py` using the same token and fixed loopback endpoint |

After the source integration, Go supports DATABASE_URL/READINESS_MODE/PORT plus the backoffice database, PUBLIC_ORIGIN, ADMIN_PASSWORD_HASH and STATIC_DIR configuration; backoffice/static handlers are registered. Catalog/routes, ticket database/voice flags, gateway and private listener registration remain incomplete. The deployment variables above **do not wire those features automatically**. The Laya entrypoint/environment/file layout is a proposed handoff awaiting TASK-0010 agreement. Change its Dockerfile together with that owner's final interface. Do not satisfy imports using fixture adapters or mark a mock image healthy.

TASK-0010 must commit `intent/model/manifest.json` with this shape and supply the corresponding predownloaded bundle (weights need not be committed to git):

```json
{
  "repository": "convaiinnovations/laya",
  "revision": "<full upstream 40-character commit>",
  "license": "Apache-2.0",
  "files": {
    "LICENSE": "<sha256>",
    "config.json": "<sha256>",
    "model.safetensors": "<sha256>"
  }
}
```

List **every** tokenizer/config/weight/license asset with real hashes. The checker rejects extra/missing files, symlinks and changed content. Runtime has Hub/Transformers offline mode; no first-request weight download. The model service must honor the local model path and prove actual CPU inference independently in TEST-0012. Frozen Python dependencies must install on Python3.12 Debian amd64 without unspecified system libraries; extend the pinned image if the actual Laya package requires them.

## Provision approved resources

```sh
rtk proxy python3 deploy/staging.py provision-plan --config deploy/local/staging.json
```

Review and execute those printed commands individually as the authorized provisioning identity. They create APIs, the budget alert, Artifact Registry, four service accounts, scoped IAM, **empty** Secret Manager resources, SQL and the database. Inspect existing resources first: this is a first-provisioning plan, not an idempotent reconciler; do not ignore arbitrary command failures or blindly recreate budgets. Project billing must already be linked. No account keys, public invoker grants or login passwords are created by the plan.

Runtime gets Cloud SQL Client and access to seven specific secrets. The operator identity gets Cloud SQL Client plus its separate database secret. Builder gets repository writer; deployer gets repository reader/Run Developer and may use only the runtime/operator accounts. A human provisioner handles invoker IAM. Local builds do not need a Cloud Build logging/source role; if Cloud Build is added, scope those resources separately. Use authorized user impersonation or configured workload identity; do not grant project-wide Secret Accessor/Owner to the builder/deployer. All containers share one Cloud Run identity/network: env placement prevents accidental injection, **not** malicious sibling access through that identity.

Create fresh SQL LOGINs with separately generated passwords via an authenticated operator session. The migration login owns the schema and can run the additive migration/import; it is never used by web traffic. After the job creates tables, the operator applies the foundation's `migrations/roles.sql` and maps three separate non-superuser LOGINs to `prompt_shop_public`, `prompt_shop_backoffice`, and `prompt_shop_voice`. Do not use `migrations/local_roles.sql` in GCP or reuse reference-project accounts. Review grants with TEST-0001; runtime logins must not own tables or have CREATEROLE/DDL privileges.

Populate named secrets from protected local files (`chmod 600`), never command-line values. Example with a placeholder secret name/file, after selecting the approved project:

```sh
rtk proxy gcloud secrets versions add SECRET_NAME --data-file=/absolute/protected/value-file --project=APPROVED_PROJECT
```

Database URL example format, **not a real credential**: `postgresql://LOGIN:URL_ENCODED_PASSWORD@/prompt_shop?host=/cloudsql/PROJECT:REGION:INSTANCE`. The managed connector provides transport security; local socket clients do not need an exposed SQL port. Supply a fresh bcrypt admin hash, independent ≥32-byte ADK/Laya tokens, and the authorized Gemini API key. Record numeric versions in local config. Pin the same bridge/token version at both ends; only ADK receives the Gemini key. Never upload TASK-0003's local `agent/.env` or pass runtime secrets as build args.

## Build and render a matched candidate

Set `source_commit` to the full **committed integrated** revision. Keep base digests pinned; review the included tags/digests for Linux amd64. Leave runtime `images` null until the actual pushed digests exist.

```sh
rtk proxy python3 deploy/build.py --images deploy/local/images.json --context /tmp/prompt-shop-reviewed-context --model-bundle /absolute/verified-laya-bundle --registry REGION-docker.pkg.dev/PROJECT/REPOSITORY
```

This packages inputs and prints Docker commands without building. Use a new context path and `--execute` to build locally. Missing frontend/classifier/locks fail before Docker. Build consumes only this sanitized context. Inspect resulting images for source/env/credential/recording leakage and run real three-container startup/auth/shutdown tests before publication. Scan the actual images with the approved registry scanner; image pins alone are not vulnerability qualification. Push each `go`, `adk`, `laya` image under the source commit tag using the authorized builder, then resolve and store its **registry manifest digest**, not the local image ID, in `images`. Record real integration/build evidence in `integration_evidence`.

Set the exact HTTPS origin and a fresh `revision_suffix`. The Go gateway currently accepts exactly one origin. For first staging, use its verified service URL. On later deployments, `previous_revision` retains 100% existing traffic and exposes the candidate tag at 0%. A tagged URL is a different origin: qualify the browser origin/access plan before candidate voice testing; do not weaken origin checks or promote a tag-only origin onto the stable hostname. TASK-0008 must resolve this with the gateway owner before release promotion.

```sh
rtk proxy python3 deploy/staging.py render --config deploy/local/staging.json --images deploy/local/images.json
```

Inspect `deploy/out/service.json` and `import-job.json`. One Go ingress uses HTTP1/8080, private ADK8001/Laya8003 startup probes, Laya→ADK→Go ordering, Go `/readyz` startup and `/healthz` liveness, timeout360, concurrency10, min0/max2, total4vCPU/5GiB. These are proposed limits awaiting measured cold-start/RSS qualification. No live provider call is permitted in probes. Runtime sidecar outages must produce an explicit voice failure/typed recovery; startup checks do not prove ongoing inference health.

## Execute migration, then staging

Substitute approved project/region in each command. On an existing database, take/verify a backup first and review additive migration/rollback compatibility. Do not run import on every service startup. The job uses the same Go image digest as the service and operator-only credentials, one task, no automatic retries. The current CLI has a 30-second internal deadline despite the job's 300-second upper bound; measure migration/seed size before changing it.

```sh
rtk proxy gcloud run jobs replace deploy/out/import-job.json --project=PROJECT --region=REGION
rtk proxy gcloud run jobs execute prompt-shop-staging-import --wait --project=PROJECT --region=REGION
```

Stop on any job failure. Apply/verify SQL role grants before service startup. Record the actual execution ID, schema/catalog/map versions and seed counts. For an existing service, inspect invoker IAM **before** deployment: a private selection must remove any existing allUsers/allAuthenticatedUsers bindings through the authorized IAM owner. A manifest cannot remove pre-existing IAM policy.

```sh
rtk proxy gcloud run services replace deploy/out/service.json --project=PROJECT --region=REGION
rtk proxy gcloud run services describe prompt-shop-staging --format=export --project=PROJECT --region=REGION
rtk proxy gcloud run services get-iam-policy prompt-shop-staging --project=PROJECT --region=REGION
```

The service always keeps the invoker IAM check enabled. For approved public staging, the authorized IAM owner explicitly grants `roles/run.invoker` to `allUsers` on **this service only**. For private staging, grant only approved principals and qualify the browser access mechanism (e.g. an approved authenticated proxy or IAP setup); an IAM-protected URL alone is not browser login UX. Test microphone, cookies and WebSocket Origin through that actual access path. No unapproved public exposure is scripted.

## Evidence and recovery

Run every step of [TEST-0010](../docs/sdlc/07-tests/TEST-0010.md). Record actual HTTPS URL, revision, source/all three image digests, secret **versions**, cloud service settings, device/browser/network, actual model/ADK setup, real Laya inference, 16kHz input/24kHz output, native audible reply, grounded cards and route, interruption and clean reconnect. Typed/mocked smoke cannot pass this gate.

Before/after replacing the revision, compare durable seed/item/catalog/map versions and repeat lookup. Capture cold setup separately, bounded session/idle/setup, RSS and concurrent load. Exercise simultaneous SIGTERM/sibling failure: Cloud Run allows ten seconds; Python grace is seven, Go foundation grace five. This configuration does not itself prove websocket/provider/worker cleanup. Inspect image assets, app/request/SQL logs and representative error paths for API keys, bearer tokens, bodies, raw audio and captions. HTTP request logs can contain query URLs; never use credential or transcript query parameters. Keep evidence synthetic/redacted and access-controlled.

For an upgrade failure, retain the known-good revision and all three digests/secret versions. Route new traffic back only after confirming DB compatibility; existing sockets can persist and require restart/reconnect testing. Do not reseed, delete Cloud SQL, or attempt an automatic destructive schema rollback. The first staging revision has no rollback baseline until TEST-0010 passes. Final version tags, release/DEP execution records, measured ≤15-minute rollback and promotion belong to TASK-0008 after its gates.

At the approved cleanup date review Run services/jobs, unused image tags, secret versions, SQL and backups. Deletion protection deliberately prevents automated SQL deletion; retain/export data according to the approved policy before a separate deletion action. A date in configuration is a reminder/validation field, not an automatic cleanup scheduler.

Implementation references checked against primary documentation: [Cloud Run YAML](https://docs.cloud.google.com/run/docs/reference/yaml/v1), [container startup order](https://docs.cloud.google.com/run/docs/configuring/services/containers), [health checks](https://docs.cloud.google.com/run/docs/configuring/healthchecks), [runtime shutdown contract](https://docs.cloud.google.com/run/docs/container-contract), [traffic migration](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration), [SQL creation flags](https://docs.cloud.google.com/sdk/gcloud/reference/sql/instances/create), and [budget commands](https://docs.cloud.google.com/sdk/gcloud/reference/billing/budgets/create).


## Task 8 operator tooling

[RELEASE.md](RELEASE.md) documents the implemented source/QA/cloud preflight, named-revision promotion, whole-bundle rollback, drift checks and operation-bound smoke qualification. The existing v0.1.0 source tag does not pass deployment acceptance; Task 8 records current blockers separately from offline controller tests.
