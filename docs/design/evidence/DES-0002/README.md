# DES-0002 local implementation evidence — 16 October 2026

GPT/Codex built in `.worktrees/TASK-0004`, branch
`feature/TASK-0004-customer-portal`, based on main
`b0d0c54fab99d814ce8222e14326120c92a2e8cc`. One active builder, sync mode.
Exact assistant model version was not exposed. This is local implementation and
scoped regression evidence, not full task, cloud or release acceptance.

## Screenshots and data

| View | Actual localhost capture |
|---|---|
| Desktop, 1440 px, idle | [desktop-idle.png](desktop-idle.png) |
| Desktop, typed milk search and selected route | [desktop-route.png](desktop-route.png) |
| Mobile, 390 px, idle | [mobile-idle.png](mobile-idle.png) |
| Mobile, selected milk first and stored route | [mobile-route.png](mobile-route.png) |

All four captures use the normal Go server at localhost:8080 with the existing
PostgreSQL seed catalog and graph. No request interception or invented product
facts are used. Images were visually inspected; no horizontal overflow occurred.
Product artwork is explicitly labelled category illustration, not a SKU photo.
The screenshots contain synthetic typed search data, not shopper conversation.
The fixed mobile dock remains at the captured viewport bottom during scrolling;
full-page screenshots therefore show it partway down the full document.

## Executed automated checks

Commands run from the task worktree unless stated otherwise:

| Command | Observed result |
|---|---|
| `rtk proxy npm --prefix web run check` | Zero errors and warnings |
| `rtk proxy npm --prefix web test` | 33 unit tests passed |
| `rtk proxy npm --prefix web run build` | Static production build passed; shopper CSS 5.60 KB gzip |
| `rtk proxy npm --prefix web run test:browser` | 15 Chromium tests passed, 7.3 s |
| `rtk proxy env BACKOFFICE_TEST_DATABASE_URL=<disposable-db> npm --prefix web run test:backoffice -- --grep 'keyboard and accessibility'` | Three protected Backoffice layout/keyboard/axe checks passed at 320/768/1280 px |
| `rtk proxy env PYTHONPATH=agent <main>/agent/.venv/bin/python -m pytest -q agent/tests intent/adapter_tests` | 39 tests passed; two existing deprecation warnings |

Browser tests cover 320/390/768/1280/1440 px, zero axe violations in the tested
states, keyboard route focus, escaped provisional captions, current factual events,
late-event rejection, microphone denial, real AudioWorklet simulated capture,
44 px dock targets and virtual-keyboard clearance. Minimize/resize retain one
session, microphone and controller; Close/Escape release them and restore focus.
Missing avatar assets retain usable voice/typed controls. Reduced-motion uses a
static portrait. Speaker-only analyser unit checks cover flush/mute/drain/close,
stale level callbacks and the unchanged one-second playback limit.

Backoffice tests used a separately created, labelled Docker PostgreSQL instance
`prompt-shop-ui-qa-des0002`, loopback port 55449, synthetic credentials and database
`prompt_shop_task9`. That ephemeral container was stopped and removed afterward;
the user's durable local catalog was not reset.

## Native provider checks

The actual normal localhost origin was tested using Chromium's simulated microphone
and synthetic macOS TTS input, real Gemini Live through Google ADK, the pinned Laya
adapter, Go gateway and PostgreSQL. No captured shopper speech or provider dialogue
was persisted. Temporary local harnesses record only booleans, counters and byte
lengths. They are diagnostic runs, not the frozen 30-trial latency suite.

- Quiet Hello → general arithmetic → egg meal idea → whole-milk shelf request:
  four completed audio replies (106080, 220802, 584162 and 162720 bytes). General
  conversation and menu suggestion appeared without catalog events; the final
  grounded lookup produced the milk candidate and route with Aisle 2 / Shelf 3
  captions. No dependency error, socket closure or audio backlog was observed.
- Intentional overlap: milk was requested during the meal reply. One old audio
  reply was cancelled, then the milk route and Aisle 2 / Shelf 3 captions completed.
  The diagnostic rerun observed three audio starts and two audio ends, one current
  candidate/route, no error/backlog and an open socket before explicit End.
- Actual speaker playback opened the avatar mouth; explicit End reset it to neutral.
  These checks qualify synthetic native browser integration, not a physical
  microphone/speaker listening assessment or Safari compatibility.

## Reproduced failures and reconciliation

1. Intercepting the entire page with Playwright `route.fulfill` triggered Chromium
   local-network WebSocket checks. The same native flow on the normal Go-served
   candidate assets passed; browser security was not disabled.
2. A deterministic actual-ADK-SDK unit case reproduced a delayed provider interruption
   ACK being relabelled as the fresh turn, three times before the fix. The runtime
   now forwards provider interruption only while its current output is open; Go's
   existing new-turn marker already flushes old playback. Current-output
   interruption is still tested and forwarded. All 39 agent/adapter tests passed.
3. An initial overlap harness sampled the DOM immediately after a socket completion
   and reported no visible route. Waiting for rendered route state (rather than
   treating a received frame as a painted UI) showed the stored route correctly.
4. Two further native overlap repetitions disconnected after the greeting and before
   producing the new product route, with no browser error event. Health endpoints
   stayed ready. The cause was not established by those diagnostics; the successful
   native runs are bounded evidence, not a claim that provider interruption is
   uniformly reliable. This remains a live-voice acceptance limitation.
5. Compact mobile results initially hid the only H1 from the accessibility tree.
   The introduction is now visually clipped while retaining its semantic heading;
   both mobile axe failures were resolved in the final 15-test run.

## Scope and remaining acceptance

No public API/event schema, catalog migration, key/model/voice setting or audio
queue limit changed. The original transparent avatar, exact prompt, optimization
and 74,240-byte shared atlas are documented in
[monti-avatar.md](../../assets/monti-avatar.md). `v0.2.0` remains the immutable
pre-redesign source checkpoint.

Manual VoiceOver/Safari, physical audio listening, the frozen 30-trial latency
suite, staging/cloud promotion and full release approval remain unexecuted here.
Laya's existing frozen 19/40 result still fails its 36/40 gate. TASK-0004 and
TEST-0009 remain blocked for their broader acceptance; this UI evidence does not
change those statuses.
