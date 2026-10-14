# Private English Laya classifier

TASK-0010 implements the fixed `intent-v1` service and the async ADK adapter at `agent/tools/intent.py`. The existing Task 3 `ToolHost` owns session/turn/attempt metadata, classification completion and the matching Go ACK. Classification labels are advisory; catalog authorization and candidate/route membership remain Go responsibilities.

**Qualification is blocked.** Actual pinned inference through private HTTP and the real ADK `BlockingTool` scored **19/40**, below the required **36/40**. All 21 misses were low-confidence abstentions. They count as incorrect. The frozen corpus, question definitions and thresholds have not been tuned after evaluation. This module is not an accepted deployed voice release.

## Model and runtime

- English root checkpoint: [convaiinnovations/laya at 7b928d828b7b0e022f929d9bd2e44165aa270148](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148). No multilingual or typed-decisions sibling weights are used.
- Weight SHA-256: `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c` (842,609,210 bytes). All configuration, tokenizer, notices and provenance hashes are in [model/manifest.json](model/manifest.json).
- `uv.lock` pins the full dependency graph and wheel hashes; direct versions are in `pyproject.toml`. Linux x86_64 resolves the explicit PyTorch CPU index. Loading uses CPU, eager backend and two native threads; it never downloads weights during startup or a request.
- The pinned model card declares Apache-2.0. That repository has no root LICENSE file; the bundle retains the full Apache-2.0 notice from [the publisher package source at c73908d96ff73c0062c340a11bf7c54ec7d8bc4d](https://github.com/NandhaKishorM/laya/blob/c73908d96ff73c0062c340a11bf7c54ec7d8bc4d/LICENSE). `PROVENANCE.json` records that distinction. Publisher Python model files are not downloaded or executed. Package licenses/notices remain in the installed locked distributions; retain them and the complete model bundle in deployment.

The maximum returned choice probability is the provisional confidence score; margin is the difference between the two highest probabilities. These are uncalibrated decision scores, not the library's separate entropy-based confidence. Confidence below 0.70 or margin below 0.15 causes `low_confidence` abstention.

## Prepare and run locally

From the task worktree root, download the immutable reviewed bundle once to an absent ignored directory, verify it, and install the locked environment:

```sh
rtk proxy python3 intent/fetch_model.py --out intent/local/model-bundle --license-commit c73908d96ff73c0062c340a11bf7c54ec7d8bc4d
rtk proxy python3 deploy/verify_model.py intent/local/model-bundle
rtk proxy uv sync --project intent --frozen --python 3.11
rtk proxy cp intent/.env.example intent/local/.env
rtk proxy chmod 600 intent/local/.env
```

Set `LAYA_INTERNAL_TOKEN` in the ignored file and the same server-side value for ADK. This service needs no Gemini key; native voice still needs the separate Task 3 provider configuration. Do not put the token in a browser, Git, a command-line argument or a proposal artifact. Start from the intent directory so the relative model path resolves there:

```sh
rtk proxy uv run --directory intent --frozen --env-file local/.env uvicorn intent_service.app:app --host 127.0.0.1 --port 8003 --workers 1 --no-access-log --timeout-graceful-shutdown 7
```

`GET /healthz` returns 503 while the worker verifies, loads and warms the actual model, and 200 only when ready. Deployment binds within its private container network; expose only the Go customer ingress. Task 5 owns `intent/Dockerfile` and the deployment build inputs. Supply the complete verified bundle to its build process; do not commit weights or credentials.

## Private contract and bounds

`POST /classify`, `Content-Type: application/json`, `X-Internal-Token`, with exactly `{ "text": "..." }`; text is 1–300 Unicode characters. Browser Origins, unknown fields, malformed/duplicate JSON and bodies over 2,048 bytes are rejected. Tool callers cannot choose an endpoint, schema, labels or model.

The response has exactly `schema_version`, `intent`, `confidence`, `margin`, `abstained`, `reason`, `model_revision`. Intent is one of `find_item`, `select_item`, `repeat_directions`, `out_of_scope` or null. Failures return null intent/scores and a typed `timeout`, `busy` or `error`; low-confidence results retain the two decision scores. Neither the service nor adapter emits products, shelf locations or executable operations.

One spawned native process owns inference, with at most four waiting jobs, queue wait at most 200 ms and a 1,200 ms request deadline including body/queue/inference. Timeout or active cancellation terminates and reaps that process before replacement. Readiness stays false during recovery; no background executor work or retries accumulate. Queued cancellations remove their own job without freeing active native capacity. Worker output and access logs are disabled; request text/credentials are not recorded in evidence or event stores. Python reference clearing is lifecycle cleanup, not a secure memory-erasure guarantee.

The adapter uses only `http://127.0.0.1:8003/classify`, no environment proxy, redirect or retry, with an independent 1,200 ms cap and 2,048 byte response limit. It checks the pinned model revision and complete coherent DTO. Task 3 emits completion/abstention and waits for the current attempt's ACK before catalog callbacks; a cancelled old turn cannot authorize a new one.

## Verification and evidence

```sh
rtk proxy uv run --project intent --frozen pytest -q intent/tests
rtk proxy uv run --project agent --frozen python -m pytest -q intent/adapter_tests
rtk proxy uv run --project agent --frozen pytest -q agent/tests
rtk proxy uv run --project agent --frozen python intent/evaluate.py --model intent/local/model-bundle --out intent/local/new-evaluation.json
```

The evaluation requires port 8003 to be free and creates/stops its own service. It does not overwrite evidence. It invokes all 40 unchanged balanced fixture inputs plus 30 independent warm probes using actual weights and the real ADK tool. Only the Go ACK/catalog bridge is a fixture. `evaluation/freeze.json` preserves the original corpus/config hashes. Any future quality tuning requires a separated new holdout and an explicit review; replacing failed rows or reducing the existing threshold to claim a pass is prohibited.

Initial [actual host evidence](evidence/host-evaluation.json): macOS ARM, CPU eager/two threads, warm p95 about 267 ms, service cold readiness about 8.24 s, load-time peak worker RSS about 1.92 GiB. This workstation had eight host CPUs; thread count is not a 2 CPU quota. Raw timings, per-class accuracy, coverage, confusion matrix, package/runtime identity and implementation hashes are in the report. A later request-body cleanup fix does not modify the frozen model question or scoring; subsequent reports preserve their own exact code identity.

`qualify_container.py --image <local-image> --out <absent-report>` provides a limited 2 CPU / 4 GiB Docker resource probe with the actual English bundle. An AMD64 image running on this ARM workstation is emulated; this does not qualify native GCP performance or replace the 40-case/30-warm gate. It creates a loopback-only task container and deletes its private temporary token and owned container.

Synthetic worker/HTTP/ACK fault fixtures separately exercise overload, hard timeout, crash/load failure, cancellation, malformed output and advisory-only behavior. They cannot count as model accuracy or deployment acceptance. TEST-0012 remains failed; full native Gemini→ADK→Laya→Go→voice/UI behavior and external network privacy remain Task 6 gates after integration and deployment.

## Handoff

- Task 3 already imports `tools.intent.classify_intent` by default. No shared ADK dependency or registry edit was needed. Supply `LAYA_INTERNAL_TOKEN` to that server; its current health check does not verify Laya token/readiness, so the integration owner must coordinate dependency readiness rather than treating ADK health alone as classifier acceptance.
- Task 5 must build a final image from the reviewed source and verified bundle, inject the same private token into ADK/Laya, and verify CPU/RAM/private-port settings on the candidate environment. No cloud configuration, image push or deployment occurred in this task.
- QA must preserve the failed 19/40 result, review any separately held-out quality iteration, then run native deployment measurements and full Task 6 acceptance. Shared Go voice/catalog wiring is outside this classifier's file ownership.
