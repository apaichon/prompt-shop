# TASK-0013 evidence — repeated shelf requests and conversation turns

Base: main 88b83e480a1c233ecaf9fd775ce9e28209260294. GPT builder and distinct
GPT review pass, one sync worktree. Local real Gemini/ADK/Laya/PostgreSQL stack;
configured provider model/voice/keys and published catalog unchanged.

## Reproduced defects

- Caption/countdown updates alone did not reproduce the shelf churn. Twelve new
  voice turns invalidate portal state while preserving the product object. The
  new browser regression on baseline made **13 requests**, expected one. Some
  pending requests were aborted. The same test on the scalar-shelf-ID fix makes
  **one request**, survives pending response and renders it, with no further
  countdown/caption fetches. Changed-shelf/stale-response tests also pass.
- Existing recovery waits eight seconds even after the model has finished a reply
  withheld for missing required tools. The actual SDK network fixture regression
  failed to receive recovery within one second on baseline. Candidate sends it
  within that bound, suppresses unverified audio, and sends at most one reminder.
- Runtime recovery used only the last input transcription chunk. The SDK test now
  exercises delta and cumulative chunks and verifies the whole request in recovery.
- An intermediate native repeat-directions turn classified and called route but
  did not search. It timed out; no authoritative route or unverified audio escaped.
  The initial instrumentation does not establish the HTTP failure code. Updated
  model instructions/next-action guidance distinguish repeat lookup from selecting
  pending ambiguous candidates; added content-free tool/status diagnostics.

## Executed automated checks

- Python agent + intent adapter: 49 passed (two existing dependency deprecation warnings).
- Frontend: 39 unit and 21 Chromium browser tests passed; Svelte check zero errors/
  warnings; production build passed. Browser suite includes pending shelf, changed
  shelf, accessibility/responsive layout, turn timeout and noise/interruption checks.
- Go unchanged; no new Go-test or full release acceptance claim.

Commands (from the task worktree, shell convention `rtk proxy`):

```
env PYTHONPATH=agent:intent <main>/agent/.venv/bin/python -m pytest agent/tests intent/adapter_tests -q
npm --prefix web run check
npm --prefix web test
npm --prefix web run build
npx playwright test                       # cwd web
```

## Native baseline and retained failure

Ten text-control turns on baseline (same public WebSocket): Hello; whole milk;
repeat directions; jasmine rice; repeat; toothpaste; thank you; whole milk;
two plus two; jasmine rice. All ten completed with audio and expected route IDs,
no error or close. First received audio ms: 1053, 2225, **9272**, 2272, 1698, 1964,
**9099**, 2031, 1274, 2101. Repeat-milk route took 8642ms. This is one small
sample, not a p95 benchmark or a physical microphone measurement.

The first exploratory probe drove text controls through a UI session with an
entirely silent microphone. It hit the browser's expected 60-second mic inactivity
limit during its ninth request (eight complete replies). This was a harness issue,
not evidence of a provider disconnect. The corrected text probe uses the public
WebSocket directly, sends pings, and refreshes server activity through text requests.
It does not claim to exercise microphone capture/playout or shelf rendering.

[Intermediate candidate native run](native-text-intermediate.json): 9/10 replies,
one `TURN_TIMEOUT` on repeated milk, connection retained, one 8198ms response.
Retained before adding repeated-lookup and per-turn next-action guidance; do not
count this as a pass or remove it from failure accounting.

## Synthetic spoken input

`conversation-audio.cjs` uses real Chromium AudioWorklet capture, public gateway,
native ADK/Gemini tools and scheduled playback with a synthetic WAV. Generate the
same ten utterances above with macOS `say -v Samantha -r 165`, convert each using
ffmpeg to mono PCM16/16kHz, prepend three seconds silence, then place each utterance
in a fourteen-second slot (143 seconds total). No shopper recording is used.
Count requests for shelf previews separately from the initial category browse.
Seven catalog turns should load seven previews, one per fresh selection; general
turns and voice updates must not trigger shelf fetches. Report first scheduled
playout from last RMS>=500 input frame and maximum gap between scheduled chunks;
these timings do not measure physical speaker output or network-wide p95.

Full TEST-0008/0009 acceptance, physical-device/noisy-room quality, 30-turn latency,
cloud release and the frozen Laya accuracy failure remain unqualified/blocked.

[Intermediate spoken run](native-audio-intermediate.json) completed all ten turns,
all seven expected routes and exactly seven shelf requests, with no errors/close
and zero scheduled playback gaps. Two first-playout delays were 5386ms and 9917ms,
so this run is not latency acceptance. Recovery was then expanded from completed
withheld audio to also handle silent completed responses. Both cases now have SDK
regressions for delta/cumulative input, one reminder, no pre-tool audio, and no
retry on a delayed completion before current input finishes. A transient indentation
error during this edit was caught at test collection, corrected before service
restart, and the final full 49-test Python run passed.

## Final candidate evidence

[Final spoken session](native-audio-final.json): **10/10 complete audio replies**,
all seven expected product routes, **seven shelf requests**, no error/disconnection,
and **zero scheduled chunk gaps** on every reply. First scheduled playout ranged
1614–3357ms, median 2729ms. No runtime recovery,
tool-failure or turn-timeout diagnostic was emitted during this run. This is one
synthetic 143-second input session, not 30-trial p95 or proof that the provider will
always respond at this speed. It also does not prove every spoken location fact;
physical listening/spoken-fact qualification remains in full acceptance.

The final runtime expanded silent-completion recovery after the retained intermediate
text run. It was qualified by the final spoken run and 49 automated Python tests;
no final ten-text-turn rerun is claimed.

## Review and integration

Distinct GPT code-reviewer pass inspected the complete changed source/test diff,
new bounded transcript helper, opt-in native probes, linked design/ADR contracts
and executed evidence. Scoped PASS: preserve actual native ADK, ACK/authority,
per-turn call limits, one recovery, cleanup and input/session bounds. Frontend
changes retain pending request identity and stale-response protection. Model-visible
next-action metadata does not alter the private classifier event/schema. Diagnostics
contain allowlisted categories/tool names and numeric status only. Retained failures
and physical/cloud/30-trial gates keep full task/test acceptance blocked.

Only deployment-path CI is configured; this diff does not trigger it. Executed local
checks above are the validation, not an invented green CI run. The existing user
local-main/testing authorization applies to this reviewed bounded patch. No release
tag, DB reset or cloud deployment.
