# TASK-0006 acceptance harness

Python 3.11+ standard library only. Run from this task worktree. The harness freezes the existing acceptance inputs, checks public DTOs independently of app code, validates graph/obstacle authority and qualifies captured timing/evidence. It never deploys, logs in with a real password, changes application code or grants release approval.

## Current evidence

See [the QA findings](evidence/FINDINGS.md), [fixture audit](evidence/fixture-audit.json), [local HTTP probes](evidence/local-http.json), [source inventory](evidence/source-inventory.json) and [release recommendation](evidence/release-report.json). The recommendation is `BLOCK_RELEASE`. Passing harness/component tests does not satisfy deployed acceptance.

The foundation snapshot has 60 published products/eight aisles and 60 connected stored destinations. Three required canonical products are absent: skimmed milk, plain yogurt, canned chickpeas. Their expectations remain null with `missing_from_seed`, and all 30 original prompts are retained. Low-fat milk, Greek yogurt and baked beans are different products. The fixture audit intentionally exits 1 until the owning task supplies the correct products.

## Reproduce

```sh
rtk proxy python3 -m unittest discover -s tests/unit -v
rtk proxy python3 -m tests.qa audit --out tests/captures/fixture-audit.json
rtk proxy python3 -m tests.qa template --out tests/captures/observations.json
rtk proxy python3 -m tests.qa measure --observations tests/captures/observations.json --out tests/captures/metrics.json
rtk proxy python3 -m tests.qa report --observations tests/captures/observations.json --out tests/captures/release.json
```

Exit 0 means that command's checks passed (or a blank template was generated); 1 means failed/incomplete acceptance, 2 means malformed/unavailable input. Generating the template does not execute any benchmark. `tests/captures/` is ignored; never put credentials, cookie values, CSRF tokens, raw shopper audio/transcripts or API keys into evidence. The shipped example is deliberately empty and cannot pass.

Collect public/anonymous boundary probes against an integrated candidate:

```sh
rtk proxy python3 -m tests.qa http --url https://CANDIDATE_HOST --candidate-commit FULL_40_HEX_COMMIT --deployment-id REVISION_ID --out tests/captures/http.json
rtk proxy python3 -m tests.qa report --observations tests/captures/observations.json --http-run tests/captures/http.json --artifacts tests/captures --out tests/captures/release.json
```

HTTP probes retain all 30 positive requests, eight negative/ambiguity/validation cases, all published destinations, inactive/invalid route cases and 20 anonymous/invalid-cookie/private-boundary probes. They use fixed-origin requests, no redirects and 1.05-second pacing by default to respect admission limits. HTTP response durations are diagnostic; they never count as audible or rendered browser latency. The anonymous suite covers denial only; authenticated lifecycle/CRUD/CSRF remain separate required checks.

For an explicitly isolated loopback fixture, add `--local`; self-signed loopback HTTPS alone can add `--insecure-local-tls`. `--pace 0` is for local fixtures. Such results are tagged `local_fixture` and cannot qualify deployed acceptance. Use `--suite catalog|routes|anonymous` to isolate a probe. A failed store-map fetch blocks routing instead of inventing 60 successful paths.

## Frozen input policy

`fixtures/catalog.json` is the verbatim TASK-0001 seed at the commit in `freeze.json`. `catalog-queries.json` reproduces TEST-0001's exact 30 prompts with explicit expected-ID bindings; `intent-queries.json` reproduces TEST-0012's 40 balanced inputs. SHA-256 hashes and fixed thresholds are validated before each run. The polygon oracle allows boundary contact but rejects crossing any interior, including narrow and concave obstacles; every returned route must use real edges, exact pickup endpoints and stored coordinates/destination labels.

Return the three missing products to TASK-0001 and search/routing failures to TASK-0002. Once the dataset owner supplies a corrected committed seed, QA must review the canonical bindings, preserve the specified prompts, create a new freeze with the new seed/source/hash, and rerun the complete suites. Never replace failed prompts, rebind distinct products as synonyms, alter thresholds after holdout or reuse old measurements with a new freeze. CLASSIFIER revision and build asset hashes must come from real TASK-0010 evidence; no revision is invented here.

## Observation format and collection

Fill a fresh copy of `observations.example.json`. Declare the deployed HTTPS origin, immutable commit/revision, measurement time, actual device/browser/microphone/network, exact native model `gemini-3.8-live` and real 40-hex Laya revision. HTTP and browser evidence must identify the same candidate and frozen files. Owner-reviewed artifacts must substantiate those claims: JSON flags alone are not proof.

The `voice` array contains each frozen `catalog-XX` ID exactly once, with `suite: warm_normal`, `status: completed|failed`, `last_voiced_sample_ms`, `speech_end_source: client_capture_clock_qa_vad`, `first_actionable_audible_ms`, `first_verified_card_render_ms`, `candidate_ids`, and boolean audit fields `heard_complete_answer`, `spoken_locations_match_tools`, `ui_locations_match_tools`, `native_audio_observed`, `real_laya_before_catalog`. Timestamp the last voiced microphone sample and audible playback/card render on the same client monotonic clock, using QA/VAD annotation. Do not use server arrival, a caption timestamp, or filler speech. Null missing replies remain failures. Audit the complete heard answer, including any pre-tool claims, against actual tool facts; UI correctness cannot excuse invented speech.

`typed_render` and `route_render` each contain all 30 catalog IDs with `suite: warm_normal`, `status`, `duration_ms` and `clock_source: client_render_clock`. Measure submission or explicit selection through completed visible rendering, never request completion alone. `classification_warm` uses the same 30 IDs in a separate warm classification run, inclusive queue+inference duration and `real_checkpoint_observed: true`. Failed/time-out trials stay in their original positions; no successful rerun substitution. Nearest-rank p95 is sample 29/30. A completed-only percentile after a failure is descriptive and cannot pass.

`intent` contains each frozen `intent-LABEL-XX` ID once, `suite: warm_normal`, `status`, `duration_ms`, `real_checkpoint_observed`, `adk_classify_intent_observed`, and `result` with the exact seven-field `intent-v1` contract from DES-0001. All 40 trials count; abstentions/errors count as misses. Scores must be finite, confidence >=0.70 and margin >=0.15 for acceptance; unknown labels/revisions and inconsistent abstentions fail. Record real inference via the isolated ADK tool, not a mock or heuristic. The evaluator reports confusion, per-class accuracy, coverage, correct/40 and inclusive latency; the separate 30-trial warm series is also required.

`cold_and_faults` is prospectively separate. Each record has a unique descriptive `id`, `suite: cold|setup|fault`, `status: completed|failed|not_available`, and optional finite `duration_ms`. Review startup, permissions, outages, DB errors, interruption/cancellation, quota/expiry, resource bounds and recovery through the named manual check artifacts. Never retrospectively move slow/failed normal trials here.

Every named `manual_checks` entry is required. Its purpose in the template maps to TEST-0001/0002/0003/0005/0012. Set `status: pass` only after the accountable reviewer checks actual observations. Supply `reviewer`, matching `candidate_commit`, `artifact` (a single redacted `.json`, `.md` or `.txt` filename in `--artifacts`) and that artifact's SHA-256. Missing/changed/symlink/oversized artifacts block qualification. Capture browser viewports, keyboard and screen-reader behavior; native ADK/model/PCM and tool-order identity; barge-in/permissions/recovery; authenticated sessions/origin/CSRF/expiry/data integrity; actual checkpoint/license/resource/queue/deadline evidence; and import rollback/public read consistency. Follow the linked TEST documents for procedures. These checks cannot be inferred from component tests.

Only fully qualified evidence yields `READY_FOR_OWNER_REVIEW`. Feature-freeze, peer/high-risk human review and release execution still belong to their accountable owners. This task currently records missing dependencies and requests changes; it is not done.
