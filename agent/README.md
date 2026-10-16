# TASK-0003 private Live runtime

This package runs the configured Gemini Live model through Google ADK `Runner.run_live`.
The default model is `gemini-3.8-live`. Go owns
public admission, ticket consumption, turn epochs, candidate sets and factual UI
events. Python owns native provider audio and three explicit BLOCKING tools.

## Conversation and store tools

The assistant supports general conversation, greetings and meal/recipe suggestions.
For every user turn Gemini calls `classify_intent` with `text` and a `response_mode`:
`conversation` for chat/meal ideas, or `catalog` for finding/matching store products,
availability and shelf directions. Laya still runs once; its shopping labels and
abstentions are advisory and do not silence a conversational reply. The selected
mode is registered with the same current-turn attempt/ACK before audio is allowed.
Older callers omitting mode keep the stricter catalog gate.

Catalog mode requires search and, for a unique match, a verified route before location
audio. Starting a catalog call closes any earlier conversational audio permission.
Meal ingredients are suggestions, not promises that the store stocks them. The
assistant offers to locate an ingredient; multiple ingredients are handled one at a
time. No recipe database, inventory/price feed or vector search is implied. General
speech remains model-generated, so actual speech grounding still needs QA.

## Configuration and launch

Run from the repository's `agent/` directory. `uv.lock` pins ADK 2.11.0 and GenAI 2.30.1 plus
transitive dependencies. Python 3.11–3.13 is supported.

```sh
rtk proxy uv sync --locked
# Create .env from .env.example if absent; preserve an existing .env.
rtk proxy cp -n .env.example .env
rtk proxy chmod 600 .env
# Set GOOGLE_API_KEY, GEMINI_MODEL and GEMINI_VOICE in this private file.
# ADK_BRIDGE_SECRET must match the Go gateway secret.
rtk proxy uv run --env-file .env uvicorn prompt_shop_live.app:app --host 0.0.0.0 --port 8001 --no-access-log --ws-max-size 65536 --ws-max-queue 1
```

Configure these server-only settings in `agent/.env` locally or the ADK container's
environment in deployment:

```dotenv
GOOGLE_API_KEY=your-key
GEMINI_MODEL=gemini-3.8-live
GEMINI_VOICE=Aoede
```

`GEMINI_MODEL` accepts a model ID with an optional `models/` prefix; an unset value
keeps the default, while an explicitly empty/invalid ID prevents startup.
`GEMINI_VOICE` selects a prebuilt voice; unset/empty preserves the provider default.
Other malformed values prevent startup. The runtime captures both settings once;
restart ADK and open a fresh voice session after changes. There is no automatic
fallback to another model or voice on provider errors. Supported model/voice pairs
depend on the provider/account and still need a real audio/tool smoke after changes.
Model selection does not add SDK compatibility: a new model generation may also
require a reviewed ADK/GenAI upgrade before its audio/tool protocol is supported.
Voice selection is passed through ADK's `RunConfig.speech_config` to Gemini's
`prebuilt_voice_config.voice_name`; see the [official Live voice configuration](https://ai.google.dev/gemini-api/docs/live-api/capabilities).
The opt-in smoke reports the configured model/voice (null voice means provider default).
The root `.env` and `make start` configure PostgreSQL, not this Python process.

Only Go is public ingress. The private runtime requires a Bearer bridge secret,
rejects query parameters and validates its setup message. `/healthz` returns 503
until the API key, a bridge secret of at least 32 characters, and TASK-0010's
`tools.intent.classify_intent` adapter are available. It makes no provider, Go or
Laya calls. A key being configured is not proof of provider entitlement.

The adapter contract is `async def classify_intent(text: str) -> dict`, returning
DES-0001's exact `intent-v1` response. TASK-0010 owns `agent/tools/intent.py` and its
Laya HTTP authentication/worker integration. No production mock, automatic model
substitution or disabled-classifier path exists here. The wrapper checks output,
applies the 1.2-second deadline, registers the attempt over the bridge and waits
for the matching Go ACK before allowing a catalog callback.

The Gemini key stays in this process. Go receives only `ADK_BRIDGE_SECRET` and a
separate least-privileged ticket DB connection. Do not copy the whole agent env
file into the ingress container. Production secret injection/images remain TASK-0005.

## Tests

From the TASK-0003 worktree root:

```sh
rtk proxy uv run --project agent pytest -q agent/tests
rtk proxy env -u GOROOT PROMPT_SHOP_GO=/opt/homebrew/bin/go python3 internal/voice/check.py
```

On other machines, omit `PROMPT_SHOP_GO` and use a working Go installation. The
Go harness copies only the voice package into a temporary module, validates its
locked dependency files, runs vet and race tests, and removes the temporary
module. It does not modify TASK-0001's root go.mod or another worktree.
`VOICE_TEST_DATABASE_URL` enables the PostgreSQL test; it creates/drops only a
random `voice_test_*` schema. The WebSocket test reserves loopback port 8001.

Python tests exercise the **real ADK Runner and GenAI serialization** with a
simulated provider socket. They check concurrent-session isolation, multipart
input/output, BLOCKING wire declarations, tool ACK order, stale cancellation,
input byte accounting, schema alignment, and error/stop/overflow cleanup. Go tests
cover origin/cookies, ticket hashes/atomic consumption, callback authorization,
candidate membership, ambiguous selection, expiry, budgets, late replies and a
real local public WebSocket/private-bridge relay. Simulated provider evidence is
not actual Gemini acceptance.

## Opt-in real-model smoke

Prepare a **synthetic**, mono PCM16LE 16 kHz WAV (at most 30 seconds) saying
“Where is whole milk?”. Once GOOGLE_API_KEY is set, run from `agent/`:

```sh
rtk proxy uv run --env-file .env python -m prompt_shop_live.smoke --input-wav /absolute/path/whole-milk.wav --output-wav /absolute/path/reply.wav
```

This uses the actual native ADK/Gemini connection, with explicitly labelled
classifier/catalog contract fixtures allowed by isolated TEST-0008. The normal
application does not use those fixtures. The smoke prints only configuration,
byte counts, tool names and lifecycle counters; raw transcripts/keys are not
printed. Output audio is written only when `--output-wav` is explicitly supplied.
Listen to verify “Aisle 2, Shelf 3” and absence of fabricated facts. A transport
smoke pass does not establish spoken selection, interruption, browser microphone,
real Laya, integrated routing, or the 30-turn latency acceptance.

## Lifecycle and limits

- Four runtime sessions; fresh in-memory session, queue, model client and tool host
  per connection. Tool operations run in their own bounded shielded child tasks;
  barge-in cancels a stale operation without cancelling the ADK runner. Actual
  Stop/shutdown still cancels and joins that child. Close/cancel/await runner,
  pending tools, provider/client and
  queue; delete the ADK session on every exit. No resumption/artifact service.
- Pending ADK input is counted at enqueue/dequeue and capped at 32,000 PCM bytes
  plus 64 total queue entries. The pinned SDK socket uses one queued message and
  a 65,536-byte message cap; application output rejects >48,000-byte PCM parts and
  splits frames at 16,384 bytes. Slow writes time out after one second.
- Setup 30 seconds, session 300 seconds from provider-ready, idle 60 seconds and
  an eight-second required-tool wait per attempt. A recognized request may get
  one native ADK continuation reminder; a second expiry (or an empty/noise turn)
  returns recoverable `TURN_TIMEOUT` and seals that turn without closing a healthy
  provider connection. Late tools/audio cannot revive it; fresh speech starts a
  new turn in the same session. Go and the browser use the same RMS 500 detector;
  silence and pings do not refresh activity. Demo-device
  qualification of this threshold remains required.
- Audio is suppressed until required tool state is satisfied; transcripts never
  become catalog facts. This is not proof that native model speech cannot invent
  facts. Actual listening/output-transcript acceptance remains mandatory.

The transport queue controls use a version-qualified private GenAI attribute;
upgrade ADK/GenAI only after rerunning the actual SDK wire tests. SDK/body logging
is silenced and Uvicorn access logs should remain disabled. Original implementation;
no Monti source was copied. Reference snapshots retain their original license.


## English policy and failure diagnosis

Spoken replies stay in English, including unclear input and requests to switch
languages; silence/background noise does not choose a language. Native audio does
not support forcing `speech_config.language_code`, so this policy lives in system
instructions. Actual synthetic native caption checks are recorded with TASK-0012.

Go/browser activity requires 80ms sustained RMS500 onset and 350ms silent PCM end.
Go preserves the onset before forwarding speech, and does not forward idle PCM.
Brief noises do not cancel playback; sustained noise/echo still needs device testing.
`voice_runtime_failure reason=...` records allowlisted categories only; never log
raw provider exceptions, credentials or transcripts. Go emits `voice_session_end`
with a similarly bounded reason. Check these categories when a session disconnects.

[Current Go/Python assessment](RUNTIME-ASSESSMENT.md): Go ADK supports RunLive now,
but changing runtime has no demonstrated advantage for the reproduced detector bug.

Text-only and clicked selections send text without empty audio activity markers.
Audio activity starts only when the first PCM frame arrives; ending an unopened
audio activity is suppressed. A native provider disconnect reproduced before this
change, and the same three-turn silence/language/route probe passed afterward.
One intermediate spoken required-tool timeout remains recorded in TASK-0012 evidence.

Recoverable `voice_turn_timeout` entries record only whether classification/search/
route were attempted and classification completed. These booleans help distinguish
missing required model calls from tool failure without exposing a shopper request.
