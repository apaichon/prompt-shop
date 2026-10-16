# Voice stop/pause repair — 16 October 2026

## Report and source

The user reported that a reply stops and the UI becomes “Voice paused or
disconnected”. GPT/Codex (exact client build unavailable) worked in the TASK-0003
worktree, sync mode, from main `2a4d574b330052809374a3a0c696212c05c4e586`.
The same session serialized the TASK-0004 audio/client/test handoff; no other
builder was active. The native Gemini/ADK/Laya/catalog pipeline is retained.

## Reproduced mechanisms

1. **A failed turn closed the entire session.** In an actual native synthetic
   overlap run the gateway closed with code 1011 after 30,374 ms. Safe temporary
   probes traced Python `TimeoutError: required tools missing` → Go provider
   failure → connection close. The eight-second tool wait was fatal to the whole
   session, even though the transport was healthy. This establishes the close
   path; it does not establish why every provider turn may omit/delay a tool.
2. **Browser and server disagreed about speech.** The browser used mean absolute
   amplitude >350, whereas Go used RMS >=500. A 100 ms PCM frame at level 400
   therefore made the browser flush playback and anticipate a new server epoch
   that Go never created. Subsequent valid reply frames were discarded. A
   deterministic actual BrowserAudio callback regression failed before repair.

3. **A cancelled tool killed ADK's caller.** `ToolHost` stored and cancelled
   `asyncio.current_task()`. The actual SDK regression showed that task could be
   ADK's root runner: interruption during an in-flight classification closed the
   session and ADK reported external root-node cancellation. Tool work now runs in
   its own bounded child task behind `asyncio.shield`. Cancelling a superseded
   child returns a stale-tool result to ADK; external Stop/shutdown cancellation
   still propagates and joins the child. The same pinned Runner remains alive for
   the next classified request.

The browser now uses Go's unchanged RMS >=500 rule, including the exact boundary
and sparse-signal cases. This removes that disagreement without disabling barge-in
or inventing client factual turn IDs.

## Recovery behavior

After eight seconds without the required tool state, a recognized current request
can receive **one** continuation reminder through the existing native ADK queue.
The prompt explicitly asks for classification again after interruption and retains
the required classification/ACK/search/route boundaries. The reminder uses at most
1,000 characters of transient current input; it is not logged or stored durably.
No withheld audio is replayed, no alternate model/STT/TTS service is introduced,
and transcript text does not create product cards or directly invoke REST lookup.

An empty/noise turn, or a second incomplete attempt, gets `TURN_TIMEOUT` in the
existing current-turn error envelope. Python and Go seal the failed turn; pending
Go tool contexts are cancelled, queued output is flushed and late classification,
search/route results and audio cannot revive it. The browser ignores the expired
epoch, shows a safe “please ask again” message and keeps capture/socket active.
Fresh speech starts a clean turn on that same provider connection. Actual provider
or transport failure still releases resources and needs explicit fresh restart.
Setup 30 s, idle 60 s, session 300 s and all existing audio/input queue bounds remain.

The error schema already allows a bounded string code; this is one explicitly
handled additive value, not an arbitrary provider instruction. Only the matching
current-turn `TURN_TIMEOUT` is forwarded as nonfatal by Go. A stale failure cannot
cancel a newer turn. Model, voice, keys, classifier thresholds, stored catalog and
cloud configuration are unchanged.

## Experiment ledger

| Run | Observation and implication |
|---|---|
| Original native overlap | 1011 close; temporary content-free probes identify the tool-wait timeout and provider-ended path. Heartbeat loss and browser-only rendering are ruled out for this run. |
| Unmodified follow-up overlaps | Three passed while the failure remained reproducible in the original run. This confirms intermittent behavior; these successes did not invalidate the captured fatal timeout. |
| SDK missing-tool regression before repair | Failed waiting for continuation; old runtime closed instead. After repair, actual pinned ADK/GenAI serialization proves one retry, withheld unsafe audio, exhausted/no-input recovery and a successful next request on one connection. |
| In-flight classification interruption | Actual Runner regression failed with a closed bridge before repair. Isolated tool-child cancellation now keeps the same Runner/provider alive; explicit Stop during that same pending tool also releases everything. |
| Quiet PCM before repair | Level 400 was reported voiced by BrowserAudio while Go rejects it. Test failed. Matching RMS boundary/sparse-signal checks pass after repair. |
| Initial noise harness | It stopped early after the provider's clarification, before the scheduled arithmetic question; no application disconnect occurred. The corrected probe completed three replies. Noise alone was not accepted as proof of the fatal timeout. |
| Candidate real quiet conversation | Four complete audio replies; no socket close, error or playback backlog; greeting, arithmetic, meal suggestion and final catalog route rendered. No early catalog action. |
| Candidate real overlap | Three audio starts/two ends demonstrate old-reply cancellation; the fresh milk route and native reply completed with the stored Aisle 2/Shelf 3 reference. No error, socket close or backlog. |

Temporary probes logged only fixed error categories, event types/timing and turn
metadata. No audio, shopper transcript, key, cookie or tool argument was logged.
All `[DBG-VST]` probes were removed from the final source.

## Executed verification

| Command from task worktree | Result |
|---|---|
| `rtk proxy env PYTHONPATH=agent <main>/agent/.venv/bin/python -m pytest -q agent/tests intent/adapter_tests` | 43 passed, two existing dependency deprecation warnings |
| `rtk proxy go test -race ./internal/voice ./internal/config ./cmd/server -count=1` | Voice/config passed; server has no tests; optional PostgreSQL ticket test is not qualified by this run |
| `rtk proxy go test -race ./internal/voice -run 'TestSpeechEnergy|TestFailedTurn' -count=1` | New RMS parity and failed-turn cancellation regressions passed |
| `rtk proxy go vet ./internal/voice ./internal/config ./cmd/server` | Passed |
| `rtk proxy npm --prefix web run check` | Zero errors/warnings |
| `rtk proxy npm --prefix web test` | 35 passed |
| `rtk proxy npm --prefix web run build` | Production static build passed |
| `rtk proxy npm --prefix web run test:browser` | 17 passed, 7.6 s |

The real Go public-WebSocket/private-bridge fixture now verifies a recoverable
current-turn timeout, late output rejection, continuing heartbeat and a fresh
successful request before explicit close. Browser checks prove one ticket and
microphone survive a failed turn and quiet PCM does not swallow later audio.
ADK tests use the actual pinned Runner/GenAI serialization with simulated provider
network, covering successful/exhausted retry and in-flight tool cancellation. These fault injections are
separate from real-provider normal/overlap observations.

The native checks used normal localhost:8080, Chromium simulated microphone,
synthetic macOS TTS, actual configured Gemini Live through ADK, real pinned Laya
and the durable PostgreSQL catalog. The four quiet audio replies contained
109440, 187200, 461280 and 153602 bytes. The overlap run completed greeting and new
milk replies (109442 and 155522 bytes), cancelled the meal reply and retained an
open socket until explicit End. The legacy helper's four-response-index caption
field is irrelevant to that three-request overlap; its route-turn assertion
accepts digit or spelled-out numbers and passed the actual Aisle 2/Shelf 3 check.
Avatar movement followed playback and stopped on End. The four-turn quiet check
preceded the final tool-cancellation refinement; the final overlap check used that
refinement, which also passes the actual-Runner cancellation/Stop regressions.

## Acceptance limits

These checks repair three reproduced source failures; they do not prove every
provider/network/device combination is stable. Physical microphone/speaker echo
and VoiceOver/Safari still need manual qualification. No frozen 30-trial latency
suite or cloud acceptance was run. The existing Laya 19/40 against 36/40 gate still
fails. TASK-0003/TEST-0008 remain blocked for broader acceptance; v0.2.0 remains
unchanged. Manual checks are in
[READINESS](sdlc/09-operations/READINESS.md#step-6--test-interruption-permissions-and-reconnect).
