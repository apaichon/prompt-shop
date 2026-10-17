# TASK-0020 summary evidence

2026-10-17 bounded regression:

- Go: go test -race ./internal/voice passes; go vet ./internal/voice passes;
  cmd/server builds. Tests cover verified choices, repeated broad queries,
  same-product deduplication, no-match/ambiguity,50record retention,48KB frame,
  invalid/null/model facts, stale/failed turns, classification and session isolation.
- Python: uv run --project agent pytest agent/tests:64passed. Includes the new
  summary flow (real contract-shaped classification ACK then one empty-args private
  summary call), invalid model facts and existing cancellation/runtime tests.
- Frontend: npm test:67passed; npm run check:0errors/warnings; npm run build passes.
  npm run test:browser:39passed, followed by the3summary/follow-up checks after final
  suppression/focus corrections and one additional mobile empty-summary test.
  All40current browser cases have passed.320px/1440px summary layouts pass axe and
  overflow checks;320px screenshot was visually inspected.
- data/validate_contracts.py passes public/private/summary examples and schemas.

[native-summary.json](native-summary.json) uses actual configured Gemini/ADK/Laya,
Go/database and real Chromium playout. The probe supplies public text requests and
synthetic silent microphone capture, not physical shopper speech. Six complete
native replies: whole milk, bagel, requested summary, rice, proactive offer,
accepted summary. Three unique confirmed products retained; two summary tool calls;
one offer10426ms after playback;139played chunks/1385288audio bytes; no errors,
no repeated offer after11.5seconds and report remains after End voice.

Initial harness failures: Go integration fixture needed the running8001port freed;
a launcher config unit fixture inadvertently invoked demo-account generation in a
temporary directory without go.mod (fixture now disables unrelated auth); candidate
static serving held an old build-directory handle across rebuild (restart after
build); Chromium fake microphone needed the same fake-UI flag as existing audio
probes. None of these failures is counted as a pass. Browser fixture initially
lacked the new summary event type and used desktop status expectations for the
mobile dock; corrected and rerun. Unit timers test the exact10second boundary;
real-time browser checks allow scheduling margin.

No credentials, cookies, session IDs, raw audio, transcripts or provider bodies
are retained. No database reset or fixture seed was performed for this native run.
This check does not establish physical acoustic stability, cloud readiness, frozen
classifier accuracy or full release acceptance.
