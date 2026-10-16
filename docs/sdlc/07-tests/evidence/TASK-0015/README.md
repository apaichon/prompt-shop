# TASK-0015 verification — 16 October 2026

Base: main b3a6bca. One GPT sync builder; distinct GPT review pass. The user
confirmed computer speakers and requested optional Speaker mode with Interrupt.

## Laya measurement

`laya-latency.json`: real local adapter plus warmed pinned Laya service, 30 sequential
requests (six fixed synthetic cases repeated five times), then three four-request
concurrent batches. Sequential median 158.0ms, nearest-rank p95 206.9ms, max225.3ms;
15 classified, 15 low-confidence abstentions, no timeout/error/busy. Concurrent:
median216.8ms, p95/max330.1ms; three classified, three low-confidence, six busy.
The single-worker queue has a 200ms waiting deadline. This indicates a concurrent
capacity limitation, not multi-second sequential inference. Thresholds unchanged.

This is a latency probe, not classifier accuracy acceptance. The frozen reviewed
40-case evaluation still has 19/40 correct and coverage0.475; its normal inference
gate remains failed (`intent/evidence/host-evaluation-reviewed.json`).

`native-text-before.json`: ten public-WebSocket text turns through actual
Go/ADK/Laya/Gemini, no physical microphone/playout. 10/10 completed with audio and
expected routes, no close/errors; nine first-audio times were 1120–1421ms, one
repeat-directions turn took 8043ms (route7556ms). This separate run does not provide
per-turn classifier attribution. Fast standalone inference cannot rule out every
Laya or provider stall. The slower native turn remains an unresolved latency limit.

## Scoped frontend checks

- `npm run check`: zero errors/warnings.
- `npm test`: 47 passed, including eight new guard cases.
- `npm run build`: passed.
- `npm run test:browser`: 23 passed, including real Chromium worklet PCM,
  accessibility, sustained feedback suppression and desktop/mobile controls.
- `git diff --check`: passed.

Initial unit invocation raced Svelte configuration generation in the fresh worktree;
it executed no tests. After sync, seven new tests initially failed because the test
helper put forbidden extra keys on strict ready events. Fixing the helper produced
46/46 passing tests; no production schema was weakened. The first candidate-native
attempts failed before ready because Chromium blocked loopback WebSocket access
from intercepted candidate static assets. `candidate-network-permission-failure.json`
retains the diagnostic. The harness now grants local-network permission only for
that explicit candidate-assets option; application security settings are unchanged.

The eight guard cases exercise completion/drain in either order, temporary queue
gaps, 250ms tail, explicit Interrupt and stale frames, independent mutes, timeout,
Stop/restart, unmute halfway through a generation, and automatic interruption with mode off. The browser cases verify
zero PCM on the actual socket after sustained simulated feedback and one controller
across mobile/desktop. `mobile-speaker-mode.png` was visually checked; Interrupt
is reachable in the minimized dock, with 44px targets and no horizontal overflow.

## Limits and manual follow-up

Mode starts off. Select Speaker mode on before the conversation; it persists across
End/Restart until reload. No actual human speaker/microphone acoustic reproduction
has been captured. Full TEST-0008/0009, noisy-room/device testing, 30-trial performance,
classifier accuracy, cloud/release and spoken-fact qualification remain blocked.
Follow the computer-speaker steps in `docs/sdlc/09-operations/READINESS.md`.


## Native synthetic-feedback result

`native-speaker-feedback.json`: 10/10 completed with audio, expected routes and
seven shelf fetches; no errors, transport failure or closure. 1,981 microphone
frames replaced with sustained RMS2000 feedback during actual scheduled playback
and a 200ms synthetic tail; zero nonzero feedback frames left the browser. The
mode's 250ms guard tail covers that injected tail. Real Chromium capture/worklet,
AudioContext, public Go, actual ADK, Laya and configured Gemini were used; only
candidate static assets were intercepted. No API or WebSocket fixture was used.

First scheduled playout after the last voiced synthetic input ranged 1673–2262ms,
median1886.5ms; maximum scheduled inter-buffer gap0ms in this run. These are ten
synthetic samples, not the 30-trial or physical-speaker acceptance gate.

Reproduction from `web/` (all variables are test inputs, no provider keys):

```sh
rtk proxy env NATIVE_SPEAKER_MODE=1 NATIVE_SPEAKER_FEEDBACK=1 \
  NATIVE_STATIC_DIR=/absolute/path/to/candidate/web/build \
  NATIVE_VOICE_WAV=/tmp/prompt-shop-task13-audio/conversation.wav \
  NATIVE_REPORT_PATH=/tmp/speaker-result.json node tests/native/conversation-audio.cjs
```

The WAV is the TASK-0013 fixed ten-utterance synthetic fixture; see its evidence
for generation. Omit NATIVE_STATIC_DIR after integration to exercise Go-served
assets. This run loaded the candidate before two review corrections: clearing a
stale “Thinking…” notice on natural playback drain and resetting completion on
fresh PCM after unmuting the same generation. Unit/browser checks cover those
corrections; the retained native report honestly shows the older stale notice.
