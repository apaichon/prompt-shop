# Go ADK compatibility evidence

Executed 18 October 2026 in the isolated TASK-0023 worktree, against the configured
Gemini Live model/voice. The running shopper application remains Python ADK.
Provider keys, raw input/output audio, transcripts and session IDs are excluded.

## Stock and intermediate failures

- `unpatched-wire-race.json`: the actual pinned SDK wire omits disabled automatic
  activity detection; a race appears between GenAI Session.send writers used by
  ADK input and tool-response goroutines. Raw fixture race traces remain private
  under task tmp and are not required to expose private host paths in this record.
- `native-text.json`: stock SDK text control completes with one tool call,
  output transcript and non-silent PCM. This does not qualify PCM input.
- `native-manual-pcm.json`: stock SDK manual synthetic input times out at 55 s,
  with no transcript, tool call or audio. Cleanup succeeds.
- `native-patched-manual-pcm.json`: intermediate build with only realtime-config
  forwarding and write locking. Provider stream fails after 3407 ms without
  audio. A private, sanitized diagnostic reports WebSocket close 1007,
  precondition failure. The Go SDK still used legacy media chunks for 3.8.

## Final compatibility build

Three checked-in patches: forward RealtimeInputConfig, extend modern Gemini 3
Live input routing, and serialize Live socket writes. Original modules stay in
the Go cache. `cmd/prepare-sdk` creates ignored, hash-verified patched copies and
an explicit Go workspace. The SDK licenses/source remain in those copies.

- `patched-wire-race.json`: both actual Runner.RunLive fixture cases pass with
  race checking, required setup fields, modern input, manual activity boundaries,
  blocking function declaration and a function response. Test code additionally
  verifies interruption, mixed caption/audio/completion and explicit teardown.
- `native-compat3-manual-pcm.json`: configured model/voice, synthetic 16 kHz mono
  PCM, one real ADK acknowledgment-tool call, input/output transcripts and
  89760 output audio bytes with 44126 nonzero samples. Turn and iterator cleanup
  complete. Whole-probe elapsed 5670 ms.
- `native-compat3-text.json`: same three-patch build, text control, one tool,
  output transcript and 42242 PCM bytes with 20037 nonzero samples. Turn and
  cleanup complete. Whole-probe elapsed 2688 ms.
- `opt-in-check.json`: CLI rejects absent native opt-in with exit 2.
- `sdk-integrity-check.json`: a deliberate extra file in a generated SDK copy
  is rejected; restoring the tree allows preparation again.
- `patched-sdk-manifest.json`: pinned modules/checksums, patch hashes, original
  and patched source hashes and patched-tree hashes.
- `source-manifest.json`: SHA-256 identity for the checked-in Go probe/build
  source. It excludes SDK copies, binaries, private environment and raw audio.

## Commands and limits

From agent-go, all local shell commands use the rtk prefix:

```sh
rtk proxy env GOMAXPROCS=2 make test vet build
rtk proxy env GOWORK=off GOMAXPROCS=2 go test -race ./internal/liveprobe -run TestPinnedSDKWireCharacterization -count=1 -v
rtk proxy env GO_ADK_LIVE_TEST=1 ../tmp/go-live-probe-patched
```

The stock race characterization is intentionally failing evidence. The Makefile
tests the explicit compatibility workspace with sdkcompat, not the stock SDK.
The live command requires the existing private environment, loaded without
printing it. Synthetic PCM additionally uses GO_ADK_SYNTHETIC_PCM. The fixture
was cropped from an existing synthetic bagel request to 1.7 seconds of raw PCM;
it is not a shopper recording and is not committed.

Native runs call real provider APIs but do not play sound through a physical
speaker or test the browser/catalog/route bridge. No thirty-turn qualification,
production p95, CPU saving, cloud rollout or Go runtime cutover is claimed.
The acknowledgment tool deliberately supplies no location facts.
