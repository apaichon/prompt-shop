# TASK-0014 — fewer model round trips

Base main: 4d44f88ef40e585a121f0a424e773fc14f79403d. One GPT sync builder;
separate review pass. Native tests use the local real Gemini 3.8 Live / Aoede,
ADK 2.11.0 / GenAI 2.30.1, Laya and Go/PostgreSQL stack. No key/model/voice changes.

## Duangjai comparison

Read-only reference: `/Users/apaichon/Projects/libra/duangjai`:
reference revision `d7491f2`; `voice-agent/src/agent.js`, `voice-agent/src/model-policy.js` and the public page
at `http://localhost:5174/voice` (HTTP 200, DuangJai title). Only allowlisted model/
voice configuration was inspected; credentials and shopper content are not copied.

Duangjai uses LiveKit Agents/Google RealtimeModel for direct general conversation,
with no function tools in that agent. Its configured model is also gemini-3.8-live;
voice is selected per character. Its proactive greeting/TTS fallback is separate
from responding to shopper speech. We did not benchmark its actual replies, so
there is no claim that prompt-shop now matches its latency or that Node/Go/Python
explains the difference. No Duangjai code/assets/configuration were copied.

Prompt-shop previously asked Gemini to plan three successive BLOCKING tool calls
for a unique product: classification, search, route. Each required another provider
exchange. It now exposes one `find_product` call and executes those required local
operations inside it. General chat uses one `begin_conversation`; ambiguous choices
use `select_product` on a later turn. All remain BLOCKING with the real classification
ACK, Go validation, cancellation and original operation timeouts. The prompt is
shorter and requests concise answers. Classifier input retains the whole semantic
request separately from the concise catalog query, including repeat requests.

Separate direct local adapter timings for four fixed synthetic utterances (Hello,
whole-milk location, repeated directions, arithmetic): 224, 160, 155, 154ms. The two
shopping requests classified successfully; the two general requests abstained for
low confidence. This is four samples, not an accuracy benchmark; actual Laya remains
required and the existing frozen accuracy gate is not passed by these checks.

## Rejected experiment and intermediate evidence

Official [Live tool guidance](https://ai.google.dev/gemini-api/docs/live-api/tools)
describes asynchronous tool scheduling. The initial experiment declared general
conversation NON_BLOCKING with a SILENT acknowledgment while preserving the current
factual gate. Native [text evidence](nonblocking-rejected-text.json) returned all
seven store routes with first received audio 1075–1661ms, but all three general
turns completed without audio. This experiment failed and was removed. The evidence
does not isolate whether provider scheduling or gated output caused silence; it is
not a supported or shipped fast path.

The subsequent all-BLOCKING [intermediate microphone run](native-audio-intermediate.json)
completed 10/10 replies, seven correct route IDs/seven shelf fetches, no error/close
and zero scheduled playback gaps. First scheduled playout 2257–2629ms. It preceded
the final addition of separate request text to the lookup schema; retain it as
intermediate evidence, not final-code qualification.

## Reproduction

Prefix commands with `rtk proxy`. Run Python checks from the task/repository root:

```
env PYTHONPATH=agent:intent <main>/agent/.venv/bin/python -m pytest agent/tests intent/adapter_tests -q
```

From `web/` against the running real local stack:

```
env NATIVE_VOICE_WAV=/absolute/path/conversation.wav NATIVE_REPORT_PATH=/tmp/voice-audio.json node tests/native/conversation-audio.cjs
env NATIVE_VOICE_TEST=1 NATIVE_VOICE_SCENARIO=selection NATIVE_REPORT_PATH=/tmp/voice-selection.json node tests/native/conversation.cjs
```

Use the same synthetic ten-utterance WAV recipe and input as
[TASK-0013](../TASK-0013/README.md#synthetic-spoken-input): actual Chromium capture,
Go activity detector, ADK/Gemini, actual tools and scheduled browser playout.
First playout is measured after the last RMS≥500 captured frame, not physical speaker
output. Expected route IDs and audio completion do not prove every spoken fact.
Selection scenario uses public WebSocket text controls: Hello → ambiguous milk →
choose a returned candidate by name. No microphone/playout claim for that scenario.

## Manual follow-up

Refresh localhost:8080 and start a new voice session. Say Hello; ask a general
question and a meal idea; locate whole milk; repeat directions twice; ask for milk
and select one of the offered products; interrupt a reply and ask for rice. Check
English speech, agreement with the displayed shelf, continued listening and one
shelf fetch per new selected route (no caption/countdown request loop). End voice
and verify the microphone indicator stops. Run on the user's actual browser/mic/
speakers; synthetic capture does not reproduce room echo or device/network issues.

Full TEST-0008/0009, physical-device/noisy-room listening, 30-trial performance,
classifier accuracy and cloud-release acceptance remain blocked. Only local scoped
validation is recorded here; deployment-path CI is not applicable to this diff.


## Retained ten-turn timeout and diagnostics

[native-audio-timeout.json](native-audio-timeout.json), after adding complete request
text to lookup: 9/10 audible completed replies; the tenth request reached the
existing bounded TURN_TIMEOUT without closing the connection. Six expected routes/
shelf fetches, two scheduled chunk gaps (101ms and 85ms). Content-free diagnostics
showed `tool_deadline` recovery, then classification/search/route all uncalled.
This establishes that no private operation began, not why the model failed to call
it. It does not establish Python/Laya saturation or an HTTP shelf loop.

Added content-free `voice_flow_rejected` diagnostics distinguishing invalid arguments
and a repeated flow in the same turn. Invalid-argument tool responses now name the
required fields so the model can correct its call. This is diagnostic/recovery
clarity, not a proven fix for the retained timeout. No raw args, transcripts or keys
are logged. Failed runs stay in the ledger and full stability remains unqualified.

[Ambiguous selection](native-selection.json): native Hello → milk → named choice
completed 3/3 audio replies, three candidates with no premature route, then exactly
the chosen route, no error/close. First received audio 1605–1883ms. Public text
controls, not synthetic or physical microphone input.


## Confirmed missing-audio recovery gap

[Native text probe before the recovery fix](native-text-empty-and-stall.json):
Hello and thanks reported completion with **zero audio**, while the tenth route was
ready in 591ms but first audio arrived only after 25,342ms (after the probe deadline,
so completion failed). Earlier catalog replies started in 879–1287ms.

Code inspection confirmed that tool success disabled the required-tool watchdog,
even if no spoken audio followed; turn_complete with an open factual gate was
forwarded without checking for any audio. The final runtime tracks first audio
separately. It immediately retries an empty completion, or retries missing first
audio at the existing eight-second deadline. Only one continuation per turn total;
when current tools succeeded, use those results without re-running tools. Second
empty completion/expiry emits recoverable TURN_TIMEOUT and keeps the session alive.
The conversational tool also returns a fixed next-action instruction to answer now.

Four actual ADK/SDK fixture cases cover silent completion vs stalled audio, recovery
vs repeated failure, exactly one classification/tool result, no premature completion,
no duplicate continuation, and preserved connection. Existing barge-in, missing-tool,
failed-turn, cleanup and wire-bound tests continue to run.


## Final scoped checks

Python agent + intent adapter: **66 passed**, two existing dependency deprecation
warnings. Coverage includes actual ADK/GenAI wire declarations, complete request vs
query, classification ACK ordering, unique/ambiguous/empty results, route errors,
invalid args, duplicate flows, cancellation between search and route, current-turn
audio recovery, no duplicate tool calls, bounded retry and session cleanup.
`node --check web/tests/native/conversation.cjs` and `git diff --check` pass.
No production web or Go source changed; their previous suite passes are not claimed
as new runs in this task.

[Final ten-turn text session](native-text-final.json): 10/10 complete audible
responses, all seven expected routes, no errors/close. First received audio
1621–1858ms; this measures the public WebSocket with text input, not microphone
playout. The prior silent/25-second stalled run remains recorded above. A passing
sample is not proof that all future provider turns will be this fast.


[Final spoken session](native-audio-final.json): **10/10 complete audio replies**,
all seven expected routes, exactly seven shelf fetches, no error or disconnection.
First scheduled browser playout **1542–1878ms, median 1687ms**. Nine replies had
zero scheduled gaps; one had a 64ms gap. No runtime recovery/tool-rejection/failure
was logged during final text/spoken sessions. These runs exercise the real provider
but do not deterministically trigger the new recovery; SDK fixture tests do.

For context, TASK-0013's final run with the same synthetic WAV/harness had median
2729ms and range 1614–3357ms. These are separate small samples, not a controlled
Duangjai comparison or p95 acceptance. Do not conceal the retained intermediate
timeout, empty replies or 25-second stall, and do not claim perfect playback.


The first [English/silence check](english-rejected.json) returned Thai after an
explicit request for Thai, then mixed language on the next lookup. The shortened
prompt had omitted the original explicit “even if the shopper asks for another
language” policy. Restored that clause and strengthened the actual SDK wire test.
The ten-turn latency samples above precede this final English-policy restoration;
no transport/tool/recovery code changed after those samples. Retain the failed
language check rather than treating ordinary English-input replies as policy proof.


[Final English/silence check](english-final.json) passed on the final prompt: all
three replies had audio and English captions without Thai script, including the
explicit Thai-language request and subsequent whole-milk lookup. Quiet before and
after speech, verified route present, no errors or disconnect. The full 66-test
Python/adapter suite passed again after the policy restoration.
