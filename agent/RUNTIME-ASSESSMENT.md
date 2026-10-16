# Python versus Go for the Live agent — 16 October 2026

Keep the current Python agent while fixing the measured turn-control defects.
A Go implementation is viable; it is not a demonstrated stability or latency fix.
This assessment is source/feature analysis, not a Python-versus-Go A/B benchmark.

## What was checked

- Current app: google-adk 2.11.0 / google-genai 2.30.1 on Python 3.11. Go already
  owns the browser WebSocket, admission, turn authority and catalog/route tools.
- Official [Go releases](https://github.com/google/adk-go/releases/tag/v2.6.0)
  identify v2.6.0 as the current v2 release (13 October 2026).
- Its [runner source](https://github.com/google/adk-go/blob/v2.6.0/runner/runner.go)
  implements RunLive, returning a LiveSession and event iterator. Its
  [Live API types](https://github.com/google/adk-go/blob/v2.6.0/agent/live.go)
  include realtime PCM/activity requests, speech/transcription configuration and
  save-blob control. Earlier repository assumptions about absent Go Live support
  are outdated; SSE support is not the basis for this conclusion.
- Google's [native language guidance](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
  says native audio chooses language automatically and does not accept an explicit
  language code. That provider constraint applies in either implementation language.

| Question | Python agent now | Go alternative |
|---|---|---|
| Native ADK streaming | Existing run_live with tested tools and cleanup | Current RunLive exists; application compatibility still needs qualification |
| False interruption from 20ms noise | Reproduced in browser/Go activity control; fix is shared onset hysteresis | Would inherit this bug if the same detector were ported |
| Language changes | Strengthen session instructions and avoid noise/idle activity | Same Gemini behavior; changing language runtime cannot enforce English |
| Process/bridge overhead | Separate Python runtime over authenticated loopback WS | Could embed ADK in Go and remove a process/hop; benefit is unmeasured |
| Laya | Actual isolated Python inference service | Still needs current Laya service unless a separately qualified implementation replaces it |
| Performance | Prior four-turn native sample available, no CPU/GIL saturation profile | No equivalent app benchmark or proved speedup was run |
| Rewrite work | Existing classification ACK, tool/turn gating, timeouts and cleanup retained | Must port and re-test all of those controls and native model/version settings |

## Confirmed defect and limits

The baseline client flushes valid playback on one RMS500 20ms frame. The regression
failed with an extra flush before the fix, then passed with 80ms sustained onset.
The Go relay had the same onset policy; a language rewrite alone leaves this path
unchanged. Both sides now use PCM duration for onset/end, with bounded replay of
onset frames after activity_start so the first syllable is retained. Idle/single
impulse frames never reach the provider. Energy duration rejects short noise bursts;
it is not a neural speech/echo classifier or a guarantee against sustained noise.

Initial log counters contained no provider failure, but a native text-only probe
subsequently reproduced provider_api_error and a closed connection. The text path
emitted empty audio activity markers. After deferring activity start until actual
PCM and omitting empty activity end, the same native probe completed three replies,
including English despite a Thai-language request and verified milk directions.
A separate spoken four-turn run still had one recoverable required-tool timeout;
this does not establish full stability or explain every physical-device disconnect.
Allowlisted diagnostics now distinguish provider/API/queue/timeout/transport reasons
without storing speech or raw exception strings.

## Migration criterion

If Go consolidation remains desirable, build a candidate behind the existing private
bridge contract and test it against the same configured Gemini model/voice, actual
Laya, PCM, tool authority and browser workload. Measure at least 30 warm turns,
first audio/card p50/p95, interruption/recovery success, connection failures,
CPU/RSS and cold setup separately. Include silence, accent/noise, mid-sentence
pauses, concurrent sessions, Stop and forced provider closure. Adopt Go only after
functional parity and a useful measured gain; current results do not establish that.


Final scoped native rerun after clarifying that a pause ends the shopper's request
(and should trigger a reply) passed all four spoken requests without errors/closure
or scheduled chunk gaps. The English/silence probe passed again. Failed intermediate
runs remain in TASK-0012 evidence; a final pass is not a causal prompt A/B study or
full stability qualification.
