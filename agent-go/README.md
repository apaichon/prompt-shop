# Go ADK compatibility build

ROADMAP-0003 / TASK-0023, milestone 1. This is an isolated compatibility probe,
not the shopper runtime. The local application still uses Python ADK.

## Dependencies and observed gaps

- Go ADK `google.golang.org/adk/v2 v2.6.0`
- GenAI `google.golang.org/genai v1.74.0`
- Go toolchain `go1.26.9`

The unpatched ADK exposes `RealtimeInputConfig` but does not forward it into the
Live connection setup. Monti needs disabled automatic activity detection to use
its manual `ActivityStart`/`ActivityEnd` contract. Stock GenAI also writes to the
same Gorilla socket concurrently from ADK input and tool-response goroutines.
`go test -race` reproduces the race. A stock real-provider manual-PCM probe timed
out with no tool call, transcript or audio. A text-controlled probe did complete.

Go ADK also restricts modern audio/text fields to model names containing gemini-3.1.
The working Python runtime recognizes Gemini 3.x Live. A two-patch native run
still failed with provider close code 1007 while Go used legacy media chunks.

The SDKs therefore need the three explicit patches in `compat/` for this experiment:

1. Forward ADK's requested realtime input config.
2. Extend modern Gemini 3 Live audio/text wire handling to the configured 3.8 model.
3. Serialize GenAI content/audio/tool-response socket writes with a session mutex.

These patches do not bypass ADK, alter the configured Live model or replace
native audio. They do not qualify a full application port by themselves.

## Reproducible patched SDK workspace

Run from this directory:

```sh
rtk proxy env GOMAXPROCS=2 make test vet build
```

`cmd/prepare-sdk` checks module versions/checksums and exact source-file hashes,
copies upstream source to ignored `.sdk/` directories and applies the checked-in
patches with zero fuzz. The upstream module cache is never edited. The generated
manifest records original and patched source hashes plus patch hashes. Repeat
preparation refuses stale or changed copies. The workspace and build tag are
explicit in the Makefile, and wire tests verify the expected setup field.

The production API's root go.mod and the Python dependencies remain unchanged.
Stock dependencies remain represented in this module's go.mod/go.sum. The local
workspace deliberately substitutes the documented patched copies during checks.
Both upstream projects supply their original license/provenance in those copies.

To reproduce the stock characterization, use `GOWORK=off` and omit `sdkcompat`:

```sh
rtk proxy env GOWORK=off GOMAXPROCS=2 go test -race ./internal/liveprobe -run TestPinnedSDKWireCharacterization -count=1 -v
```

That command is expected to expose the upstream race. A non-race characterization
test passing with the stock SDK is not a passing migration gate.

## Opt-in real-provider probe

Build first. Load the existing private provider configuration into the process
environment without printing it. Preserve `GEMINI_MODEL` and `GEMINI_VOICE` from
the working runtime. The CLI uses the Gemini API `v1alpha` endpoint as Python does.

```sh
rtk proxy env GO_ADK_LIVE_TEST=1 ../tmp/go-live-probe-patched
```

For a synthetic **16 kHz mono signed 16-bit little-endian raw PCM** fixture, set
`GO_ADK_SYNTHETIC_PCM` to its private local path. A WAV container is not raw PCM.
Input is limited to 20 seconds. The probe sends explicit activity start/end and
paced 20 ms chunks. It uses a single acknowledgment tool that cannot return store
facts. The PCM mode requires input/output transcript events, non-silent output
PCM, one tool call, turn completion and iterator cleanup.

Native output is JSON with SDK/model identity, compatibility patch names,
status, booleans and counts only. It never writes transcripts, raw output audio,
tool arguments, session IDs, credentials or raw provider errors. The CLI discards
SDK logs, bounds its context to 55 seconds and its process to 60 seconds. These
process bounds do not fix the SDK's context-insensitive WebSocket dialer for a
future long-running server.

Native probes are excluded from CI and make no physical-speaker, noisy-store,
30-turn parity, production p95, CPU-saving or deployment claim. See TEST-0020 and
the TASK-0023 evidence directory for actual observed outcomes and remaining gates.
