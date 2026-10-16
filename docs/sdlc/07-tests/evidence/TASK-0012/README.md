# TASK-0012 investigation ledger — 16 October 2026

## Scope and current conclusion

English-only instructions and a confirmed transient-noise cancellation fix are
implemented. Current Go ADK supports Live, but there is no Go/Python A/B speed or
stability benchmark. See agent/RUNTIME-ASSESSMENT.md. The reported physical-device
disconnect is not fully reproduced or resolved; do not claim universal stability.

## Breadcrumbs

1. Read current runtime, actual SDK/queue/tool cancellation, browser PCM/client and
   Go relay paths. Both browser and Go began a turn on a single RMS500 frame.
   At 20ms capture that can flush a reply after a short loud impulse. Current
   original logs had no recorded provider failure/traceback, but did not distinguish
   failure reasons; that absence is not proof of health.
2. Added a focused regression using a real VoiceClient with fake transport/audio:
   existing behavior flushed once too many on a single 640-byte (20ms) voiced frame.
   Expected unchanged flush count failed (actual 2 versus expected 1).
3. Introduced 80ms sustained onset and 350ms silent end based on PCM byte duration
   in browser and Go. Go buffers onset until activity_start, preserving all first
   samples; idle frames/isolated impulses never reach the provider. Added matching
   threshold/reset/end/bounded-onset tests and a real browser capture-noise test.
4. English remains a system policy: do not auto-switch for silence, noise or accent;
   answer in English even when asked for another language. Actual SDK serialization
   asserts the policy reaches setup and no unsupported language_code is supplied.
5. Added allowlisted failure categories and numeric provider HTTP status, without
   exception payloads, shopper text, audio or secrets. Go session ends distinguish
   known policy/deadline/provider/transport categories with no raw error text.
6. First real native silence/text-language probe: quiet start passed, but text-only
   Hello yielded DEPENDENCY_UNAVAILABLE and closed. Safe diagnostics identified
   provider_api_error / provider_ended. A baseline SDK wire regression then proved
   empty activityStart/activityEnd markers surrounded text with no PCM. Defer audio
   activity start until first PCM, and never close an unopened activity for text.
   This also covers the clicked voice-selection path. The baseline regression failed;
   the candidate regression passes. Native confirmation is recorded below.
7. An intermediate four-turn real-microphone-file run completed greeting, arithmetic
   and meal idea, but the milk request timed out (TURN_TIMEOUT) with no connection
   closure/backlog. This failed run is retained: 3/4 completed, 4 input transcripts,
   3 audio starts/ends, no catalog event. Do not discard it or count it as a full pass.
   It shows required-tool/model-response reliability still needs qualification.

## Scoped automated checks

- Go voice race tests and vet: pass.
- Frontend: 39 unit tests, 20 Chromium tests pass; Svelte check zero errors/warnings;
  static build passes. Existing responsive/axe/state/Stop coverage retained.
- Python agent/actual SDK/intent adapter: 45 tests pass after the text-activity fix.
- No model/provider/voice changes, no database reset or catalog edits.

## Remaining qualification

Sustained noise/echo may still look like speech to an energy detector. Physical
microphone/speaker, idle/session deadlines and manual accessibility remain open.
A recoverable required-tool timeout is still observed in the intermediate run;
this work does not qualify the 30-trial performance/reliability gates. Real provider
language checks assess generated captions and native audio presence, not an acoustic
language-verification system. Full linked TEST-0008/0009 acceptance remains blocked.


## Native confirmation after text-activity correction

The same real Gemini + native ADK + actual Laya probe passed:

- 8 seconds of initial synthetic silent microphone: no audio reply.
- Text-only Hello: completed native audio, 103,202 bytes; English caption words.
- Request to reply only in Thai: completed native audio, 200,160 bytes; English
  caption words and no Thai script. Output language is a model instruction, not
  hard acoustic validation or a reason to send unsupported language settings.
- Whole milk request: completed native audio, 160,800 bytes and verified route.
- 8 seconds after the last reply: no extra audio start; no error or closure.

`web/tests/native/english-silence.cjs` requires an explicit synthetic silence WAV;
output contains booleans/counts only. No provider key, raw speech or caption text
was stored in evidence.

The separate real-provider barge-in run passed: three audio starts, two ends,
interrupted old audio discarded, followed by a completed grounded milk route in the
same open session, no error/backlog, avatar stopped after End. The generic four-turn
fields in that reused barge harness are not its pass criteria: it intentionally
interrupts the long middle reply; `interruption_recovered` and `cancelled_audio_observed`
were true. Do not interpret its early_catalog/fewer-completions fields as normal
four-turn test results.


A subsequent fixed-schedule four-utterance WAV run completed only its last two
replies (no error/closure; first audible response was turn 3). This run fails the
normal four-turn functional criterion and is retained. The initial "wait quietly
when silent" wording was ambiguous about the pause *after* a received request.
It was tightened: answer promptly when the shopper finishes; wait for a new request
only after answering. Silence must not suppress a pending answer. Final rerun below.


## Final native rerun with clarified reply/silence policy

Final spoken four-turn synthetic-microphone run passed all four replies: greeting,
arithmetic, meal suggestion and stored whole-milk directions. One current session,
four audio starts/ends/completions, one candidates/route event, correct visible and
captioned stored location, no early catalog events, no error/closure/backlog, avatar
animated and returned idle on End. First scheduled playback per turn: 1635.0,
1551.1, 1702.8 and 2556.1ms; all measured scheduled inter-chunk gaps were zero.
This single functional rerun ran alongside the language check and is not a controlled
performance comparison, p95 benchmark or proof of the cause of earlier failures.

The final English/silence/text-language probe also passed: three completed replies
with native audio (108,002 / 204,480 / 196,800 bytes), English caption words and no
Thai script, verified milk route, quiet initial/post-reply windows, no error/closure.
The two intermediate failed normal runs remain above; don't replace their accounting
with the final pass. Physical-device and repeated-turn reliability remain unqualified.
