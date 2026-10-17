# Voice gateway integration handoff

Owned by TASK-0003. TASK-0001's integration owner wires these constructors after
foundation acceptance; this branch does not edit shared server/config/schema or
root Go lockfiles. TASK-0002 supplies the `Catalog` adapter with published-only
snapshot reads and a DB sub-deadline of 750 ms.

```go
voiceGateway, err := voice.NewGateway(voice.GatewayConfig{
    Origin: "https://the-configured-demo-origin",
    BridgeSecret: bridgeSecret,
    Enabled: voiceEnabled,
}, voice.PostgresTickets{Pool: ticketPool}, catalogAdapter)
// Handle err. Register before the foundation JSON 404 fallback:
httpserver.Dependencies{Register: voiceGateway.Register /* other checks/config */}
// Separate loopback listener; never mount private tools on the public router:
private := voice.PrivateServer(voiceGateway.Registry, catalogAdapter)
// Run private.ListenAndServe; shut it down with the process context.
```

Use a separately configured ticket principal and one-connection pool, with
TASK-0001's voice-ticket grants. The operator purges expired tickets daily using
`PostgresTickets.Purge`; the runtime admission principal does not need DELETE.
No schema changes are requested. Shared dependency request:
`github.com/fasthttp/websocket v1.5.12`. `testdata/harness.mod` and `.sum` use the
foundation handoff's Go 1.26.9, Fiber, pgx and transitive pins plus that dependency.
The test harness is temporary build scaffolding, not an extra deployed module.

Endpoints: POST `/api/voice/sessions`, GET `/ws/voice` with exact configured Origin,
secure single-use HttpOnly cookie and `prompt-shop.voice.v1`. No query parameters.
The public listener never receives the Gemini API key. Four active connections;
per-IP ticket issuance uses burst 2 and refill 6/min, with a bounded 1,024-key map.
Shared-instance limits do not constitute a global provider spending cap.

Private bridge: authenticated `ws://127.0.0.1:8001/live`, first message
`{type:"setup",session_id,language:"en-US",turn_id:"turn-0",tool_capability}`.
Wire turns are `turn-N` strings; audio generations are `generation-N`. The Go
monotonic epoch advances on meaningful speech onset, text or explicit selection.
Gateway-only `begin_turn` / `activity_end` control messages each carry session_id
and turn_id; `text` additionally carries text. Python `provider_ready` means ADK's
actual provider handshake completed. These internal controls extend the foundation
setup/classification fixtures without changing public events.

`classification_completed` must register in Go before its matching
`classification_registered` ACK. Python waits for that ACK before callbacks.
The completed event also carries `response_mode: "conversation" | "catalog"`.
Conversation mode unlocks general speech after the recorded attempt even when
Laya abstains; catalog mode (also the missing-mode default) keeps the search/route
gate. Starting any catalog callback closes conversation permission, and each new
turn resets it. Laya labels never grant access or supply store facts. This extends
the private contract only; public events and least-privileged callbacks are unchanged.
Callback bodies contain `{session_id,turn_id,call_id,classification_attempt_id,args}`
with a per-connection capability in Authorization. Fixed loopback POST routes:
`/internal/tools/search_catalog` and `/internal/tools/get_product_route` only.
The gateway owns and emits candidate/route events from service DTOs. A bridge
cannot submit arbitrary cards/map actions. Candidate expiry is 60 seconds; an
ambiguous search requires a later shopper turn or explicit selection.

Foundation contract snapshot source: TASK-0001's 2026-10-13 local handoff,
`data/contracts/live.schema.json` and `private.schema.json`; hashes are recorded
under `agent/tests/contracts/provenance.json`, including the 16 October response-mode
amendment and its original handoff hash. Final foundation/Grok acceptance
and a clean rebase remain integration gates.


## Recoverable turn failure

ADK may send the existing `error` envelope with `code: "TURN_TIMEOUT"`, matching
`session_id` and the current `turn_id`. Go seals/cancels only that turn, flushes its
queued output and forwards a normalized safe message. Late classification, tools
and audio cannot unlock the failed turn. A fresh speech/text/select turn resets
this state; the provider socket, microphone and admission slot stay alive within
the existing session/idle limits. Unknown/fatal provider errors still close the
session. The browser treats only this explicitly allowed code as turn recovery.
The public JSON error shape is unchanged; its code string already permits this
additive value. Browser capture uses the same RMS >=500 speech test as Go.


TASK-0020 adds capability-protected POST /internal/tools/get_conversation_summary
with args={} and the existing classification ACK/turn/call budget. It reads only
bounded Go session memory, emits the server-authored summary event and unlocks
that turn's audio. Successful search/route operations emit requested=false summary
snapshots; explicit recap emits requested=true. Bridge/provider frames cannot
supply summary facts. Entry fields: query,status,catalog_version,products. Statuses:
confirmed,needs_choice,not_found,unconfirmed. Max 50 records and 48 KB snapshot; truncated
states discarded earlier history. Close clears memory. No database writes.


TASK-0022 adds a private ADK-to-Go `response_ready` event carrying only
`session_id`, `turn_id`, and `classification_attempt_id`. After a bounded shopper
flow finishes with a clarification or tool error, ADK sends this control before
any audio. Go accepts it only for the current, classified, unfailed turn and does
not forward it to the browser. It releases speech but never creates catalog,
route, or summary facts. Public browser controls cannot send this event. Both
services must be restarted together when installing this amendment.
