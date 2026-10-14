# TASK-0001 contract handoff

These are **fixtures**, not working search, voice or backoffice handlers. Only `/healthz`, `/readyz` and normalized JSON 404/errors are implemented in the foundation server. The seed is 60 published products plus one draft and one archived fixture across eight aisles; all published products are mapped. English is the only enabled locale.

`api/openapi.yaml` is OpenAPI 3.1 written in JSON (valid YAML 1.2). `manifest.json` maps public examples to its component schemas. `live.schema.json` and `private.schema.json` are JSON Schema 2020-12. Run `rtk proxy python3 data/validate_contracts.py` with jsonschema installed. The example Laya confidence and model revision are synthetic and provide no real-inference evidence.

## Public transport

Customer REST and the browser socket use the same origin. Exact configured Origin is required for ticket issuance/upgrade and admin mutations. Tickets expire after 30 seconds, are single use, and live only in the secure HttpOnly cookie; no URL credentials. Maintainer cookies expire after eight hours; mutations also require X-CSRF-Token. JSON request objects must reject unknown fields, including case variants; the importer already enforces this. API bodies follow OpenAPI limits. Error responses contain X-Request-ID, normalized error code/message/retryable, and no raw SQL/provider errors.

Browser JSON: text/select/stop/ping only. Gateway JSON: ready, transcripts, candidates, route, audio_start/end, interrupted, turn_complete, error, session_ending, pong. `live-events.json` lists individual shape examples, **not an executable conversational sequence**. Session/turn/generation IDs must be checked against current state; schema validity alone never grants authorization. `turn_id` and `generation_id` are opaque server-generated strings, not counters the browser can select.

Binary audio is PCM16LE mono: browser input 16 kHz, 3200 bytes normally, even length, maximum 6400 bytes/frame; server output 24 kHz, maximum 16 KiB/frame. Browser JSON maximum 4 KiB/frame. Audio buffering is at most one second (input 32000 bytes, output 48000 bytes). `audio_start` establishes the generation for following ordered binary frames. Interruption invalidates/flushes it. Setup 30 s, live session 300 s from ready, idle 60 s, heartbeat 20 s with 10 s grace. See DES-0001 for quotas and admission rules.

## Private transport

| Link | Address/authentication | Fixture/schema |
|---|---|---|
| Go to ADK | `ws://127.0.0.1:8001/live`, Bearer shared bridge secret | `bridge-setup`; tool capability is trusted host context, never model args |
| ADK to Go search | `POST http://127.0.0.1:8002/internal/tools/search_catalog`, Bearer per-session capability; max 4 KiB | `search-callback` / `search-tool-response` |
| ADK to Go route | `POST http://127.0.0.1:8002/internal/tools/get_product_route`, same scoped capability | `route-callback` / `route-tool-response` |
| ADK to Laya | `POST http://127.0.0.1:8003/classify`, X-Internal-Token; max 2 KiB | `laya-request` / `laya-response` |

After `classification-completed`, Go registers the attempt on the current session/turn and sends `classification-registered`. ADK must await this matching ACK **before** the HTTP callback. New turn, interruption or revoked capability cancels dispatch; missing/stale ACK rejects catalog calls. Classification is advisory, never product/location authority or permission. Timeout/abstention remains explicit. Go private listener binds loopback and is never registered on public Fiber routes. All placeholders labelled fixture are non-secret test values.

TASK-0003 and TASK-0010 implement and test these transports with actual ADK/Laya. Required native Gemini Live 3.8 remains a later task; no provider access is claimed here.
