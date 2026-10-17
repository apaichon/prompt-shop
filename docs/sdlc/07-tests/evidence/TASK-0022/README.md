# TASK-0022 verification — 17 October 2026

The source was isolated in `.worktrees/TASK-0022` from the existing dirty main checkout. No source edits were applied to main, no other task worktree was edited, and no cloud deployment was performed. The local portal at http://localhost:8080 is running the task worktree build.

## Reproductions and fixes

- Native three-turn greeting → ambiguous milk search → named selection failed before the repair: turn 3 returned audio but no expected route. After repair all three turns pass. Named selection prototypes resolve the previously abstaining phrase.
- Baseline frozen embedding set: 16/40 exact labels (24/40 tool outcomes if safe out-of-scope abstentions count). Final: **36/40 exact labels, 40/40 tool outcomes**, because four out-of-scope cases correctly perform no lookup by abstaining. This is a calibration-set result, not independent production accuracy. All labels were eligible, stressing new searches while an older selection/route exists.
- Final **warm p95 631 ms**, measured over 40 sequential real requests with persistent HTTP connection. This misses the earlier 500 ms planning target; do not relabel it as met. Prototype warm-up is outside the turn. The runtime uses 768-dimensional remote embeddings and cached prototypes, without a local transformer.
- Python formerly enabled clarification audio while Go still gated it. The ordered, private response_ready control now releases both gates for the same classified, unfailed turn. Unit tests reject unknown attempts and stale/failed turns.
- Empty searches previously retained old candidates/routes. Both are now replaced consistently with Go.
- Unique typed matches now load their route automatically; candidates can be chosen beside the map, and known aisles highlight even when walking geometry is unavailable. Route/map version checks remain mandatory.
- Mobile routes dismiss the voice dialog to reveal the map, without stopping voice. Opening the dialog again remains possible. Accessibility checks passed at five viewport widths.

## Executed checks

Run from the task checkout, with every shell command prefixed by rtk:

```sh
rtk go test ./...
rtk proxy env PYTHONPATH=agent agent/.venv/bin/python -m pytest agent/tests -q
rtk npm --prefix web test
rtk npm --prefix web run check
rtk npm --prefix web run build
rtk npm --prefix web run test:browser -- --grep 'typed flow|unique search|verified voice route|clicked voice choice|captions are escaped|mobile minimize'
rtk git diff --check
```

Results: 189 Go tests; 77 Python tests on the initial fix (plus a subsequently added, passing strong-find regression); 70 frontend unit tests; 11 browser scenarios; zero Svelte errors/warnings; build and diff check passed. After final edits: 29 embedding/shopper tests, 35 runtime tests, and 3 automatic-location/mobile-dialog scenarios passed. Browser fixtures verify UI behavior and accessibility, not real-provider quality.

## Real-provider evidence

- `native-selection.json`: 3/3 text-controlled public WebSocket turns with actual Gemini output audio; named choice route in 1112 ms, first audio in 1615 ms.
- `native-conversation.json`: 10/10 text-controlled turns with actual audio and expected routes, including repeated directions, general chat and switching products. No errors/disconnects. First audio 1461–1995 ms.
- `native-mobile-audio-final.json`: synthetic bagel speech through actual Chromium microphone capture and speaker playout, with actual Gemini Live, Gemini Embedding 2, Go catalog/route, and Svelte UI. Verifies bagels, aisle, shelf, visible path and one highlighted aisle. The earlier probe is retained separately; its shelf-label check failed before the exact-label voice instruction and spoken-number normalization.
- `mobile-map.png`: observed 390px mobile result; no transcript, audio or credential is saved.
- `embedding-measured.json`: 40 sequential requests, scores, case IDs and timing, without text or credentials.
- `resources.json`: sampled Go/ADK CPU/RSS and no listener on Laya port 8003. A process snapshot is not an A/B CPU benchmark. Laya was already stopped when this session began, so no measured CPU reduction is claimed.

The real microphone probe uses synthetic speech, not a physical handset or noisy-store test. Existing Laya release evidence is preserved. No 30-turn production acceptance or cloud qualification is claimed.

## Reproduce native checks

Set the private credential handout path through `NATIVE_ACCOUNTS_FILE`; do not put credentials in command arguments or logs. Run `web/tests/native/conversation.cjs` with `NATIVE_VOICE_TEST=1` (and `NATIVE_VOICE_SCENARIO=selection` for choice). Run `web/tests/native/embedding-map.cjs` with `NATIVE_VOICE_WAV` pointing to synthetic single-item audio and optionally `NATIVE_EXPECTED_PRODUCT`. These checks call the real provider.

The reusable `agent/evaluate_embeddings.py --live --output <report.json>` requires `GOOGLE_API_KEY` in its environment. It emits IDs, scores and timings only. Load the private agent environment securely; never paste its values into a report.

## Local operation

The running source is the TASK-0022 checkout, not main. Use `rtk make mvp-status`, `rtk make mvp-stop` or `rtk make mvp-restart` from that checkout. The agent .env is the single source for INTENT_BACKEND. Embedding mode starts ADK and Go only; explicit Laya rollback requires its local environment and model. Do not run another checkout's launcher concurrently on the same ports.

The task branch remains uncommitted; existing main working changes remain available for an integration handoff. TEST-0019 is the repair's verification record; historical TEST-0018/REQ-0006 gates are not overwritten.

## Follow-up: captions without audible reply

The shopper reported reply text with no sound. Brave allowed sound; macOS reported built-in speakers, volume 56%, unmuted. The shopper confirmed the app's speaker-test tone was audible. A fresh isolated Brave run with the default Playwright audio mute removed produced 270240 bytes of PCM (RMS 5498), started playout, completed the bagel route and aisle/shelf speech, and had no error or disconnect. The shopper explicitly confirmed hearing Monti during this test. See `native-brave-audible.json`. This confirms audible playback on this machine in a fresh session; the earlier silent session's cause remains unconfirmed.

Muted sound now displays a crossed-out speaker icon and an explicit notice; the mobile dock also reports Sound muted. This addresses ambiguous mute feedback, not a proven root cause of the reported silence. Svelte check (zero errors/warnings), production build, and the existing captions/interruption/mute/Stop browser scenario passed. Native probe now rejects silent PCM and optionally accepts `NATIVE_BROWSER_EXECUTABLE` plus `NATIVE_AUDIBLE=1` for audible device testing.

Local rebuild note: replacing `web/build` invalidates the running Go server's `os.OpenRoot` directory capability. A post-build GET returned 404 until the verified TASK-0022 Go process was restarted; GET `/` then returned 200. Restart the local Go process after replacing the static build. ADK remained running.

## Reproduced beef result with no reply

A follow-up report identified two beef matches followed by no captions or sound. The browser showed microphone listening with the results retained. Clean synthetic beef speech and public-protocol beef selection both succeeded. Injecting seven 20 ms above-threshold noise frames immediately after the candidates event reproduced the failure: two results, zero reply PCM, no output caption, and TURN_TIMEOUT (`native-beef-noise-before.json`). The client had protected microphone input during playback only; noise during tool/response latency anticipated a new turn, cleared captions and canceled the pending answer. The corresponding regression failed before the fix.

Speaker mode now holds microphone input from utterance completion through reply preparation and playback. A verified candidates/route event also starts the hold, allowing Go's activity detector to finish when steady noise prevents local silence detection. Interrupt, mute, Stop, timeout and speaker-mode-off preserve recovery/control paths. UI labels describe the pause during preparation. No provider model, embedding thresholds or catalog authority changed in this follow-up.

After the fix, the same injected-noise scenario returns captions and audible PCM (`native-beef-noise-after.json`). The final real Brave run (`native-beef-brave-final.json`) injected eight noise frames, produced 222722 bytes for clarification, then 251040 bytes after clicking beef steak, with the expected route, one highlighted aisle and spoken aisle/shelf, and no errors/disconnection. One intermediate choice run produced audio/route but failed the exact aisle/shelf caption assertions; it is retained in `native-beef-noise-selection.json`. The subsequent diagnostic and final Brave runs passed both assertions; the intermediate wording was not retained, so its semantic correctness is unconfirmed.

Validation: 77 frontend unit tests, seven focused browser scenarios, zero Svelte errors/warnings, production build passed. The distinct follow-up review checked pending-reply hold transitions, microphone resumption, mode-off barge-in, clicked choice, stale selection, timeout and Stop/restart. Local publication preserves Go's open static directory and replaces HTML last, retaining existing logins and hashed assets. No service restart was required. The browser was refreshed to load the tested build.

Reproduce with `web/tests/native/beef-audio.cjs`: provide a synthetic beef-request WAV via `NATIVE_VOICE_WAV`, private `NATIVE_ACCOUNTS_FILE`, `NATIVE_NOISE_AFTER_RESULT=1`, and `NATIVE_CHOOSE_BEEF=1`. `NATIVE_STATIC_DIR` can test candidate static files against the live local API. The test calls real Gemini Live and embeddings; it never records a physical microphone.
