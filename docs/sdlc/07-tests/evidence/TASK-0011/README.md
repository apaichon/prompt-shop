# TASK-0011 scoped local evidence — 16 October 2026

## Reference and implementation

Read-only reference: `/Users/apaichon/Projects/libra/duangjai`, revision
`d7491f24ac335c75c8e9d7cca5d04c2801b50925`. The user spelled the directory
`duanjai`; the existing `duangjai` repository was located without modifying it.
Inspected voice-agent/src/agent.js, model-policy.js and the Sprint 18 Gemini Live
compatibility notes. Its continuous track playout informed clock-based streaming;
no source, fortune-telling logic, separate TTS chain or LiveKit service was copied.
Its model defaults and reported timings are not prompt-shop measurements. The
configured Gemini model/voice and native Python ADK/Laya remain in place.

Python now paces against an absolute clock, allowing a bounded 120ms relay lead.
Browser adds a 60ms jitter lead once per playout, with no repeated per-frame delay.
Capture frames are 20ms; browser and Go end activity at 350ms silence with the
same RMS 500 speech detector. The one-second audio cap and stale-generation
cancellation remain enforced.

## Synthetic native timing comparison

One four-turn session before and one after, using the same synthetic WAV,
Chromium fake microphone, local Go/ADK/actual offline Laya, and real Gemini API.
The WAV contains greeting, arithmetic, an egg meal idea and whole milk directions.
No shopper audio or provider keys were saved in evidence. Timing is last voiced
capture callback to first scheduled browser playback, not acoustic output latency.
Provider replies vary between sessions. This is **not** a 30-trial p95 benchmark.

| Turn | Before first playback (ms) | After first playback (ms) |
|---|---:|---:|
| Greeting | 2042.0 | 1802.3 |
| General question | 1830.8 | 1639.2 |
| Meal idea | 2001.7 | 1627.5 |
| Grounded milk route | 3284.5 | 3192.6 |
| Median, these four turns only | 2021.9 | 1720.8 |

Before: recurring scheduled inter-chunk gaps around 2.7–18.7ms, maximum 32ms.
After: three replies had zero scheduled gaps; the general answer had one 101.3ms
gap. Clock pacing removes routine relay drift; upstream/network stalls can remain.
Both sessions completed all four spoken replies, with a verified milk route,
correct stored aisle/shelf captions, no early catalog tool event, no error event,
no WebSocket closure and no audio backlog. Avatar animated and stopped on End.
The script `web/tests/native/voice-performance.cjs` accepts `NATIVE_VOICE_WAV`;
its output records timings/counts/booleans rather than shopper text or raw audio.

## Catalog and imagery

The base batch reported unchanged. The additive visual-catalog-v2 batch applied
60 new products: 120 published products, 122 total including inactive fixtures.
A second `make start` reported **unchanged** for both batches, catalog version 2,
map version 1. No reset or existing product/map rewrite was performed.
The readonly HTTP integration checked published browse, pagination bounds,
same-shelf filtering and unpublished exclusion against the actual seeded DB.
All 120 published IDs have sample artwork; five runtime atlases total 674,608 bytes.
The gallery is a browse view, separate from the three-result spoken-search contract.

## Executed checks

- `go test -race ./...`: pass (optional DB-reset suites remain opt-in).
- `go vet ./...`: pass.
- Readonly seeded catalog/HTTP integration: pass against local PostgreSQL.
- Agent/native SDK/intent adapter tests: 43 passed.
- Frontend unit tests: 36 passed; includes 20ms resampling at three source rates,
  single jitter lead, gapless scheduling, output bound and cancellation.
- Svelte check: zero errors/warnings; static production build passed.
- Chromium browser tests: 19 passed, including missing-image fallback, category
  changes, explicit browse route, shelf membership and stale shelf response.
- Existing fixture flows retain keyboard/axe/320–1440px checks.

Full manual physical microphone/speaker and screen-reader checks, cloud acceptance,
frozen classifier accuracy and 30-trial performance qualification remain open.


The separate synthetic mid-reply interruption check also passed: three audio starts,
two audio ends, an interrupted response discarded, followed by a completed verified
whole-milk route in the same open session. No error, closure or audio backlog;
avatar returned to idle after End. This uses a synthetic file, not physical speech.
Final populated gallery at 320/390/768/1280/1440px has no document overflow and the
selected gallery/shelf state has zero axe violations. Actual 390px seeded preview
also reports no overflow, no page errors, 120 unique published IDs, imagery for all
120, inactive fixtures excluded, and four current same-shelf products.

During verification, rebuilding static assets under an already running Fiber
process temporarily left its cached index referencing removed build chunks.
Restarting the owned Go service cleared that cache; the final supervisor restart
always builds before launching the server. No application workaround was needed.
