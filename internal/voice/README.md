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
Callback bodies contain `{session_id,turn_id,call_id,classification_attempt_id,args}`
with a per-connection capability in Authorization. Fixed loopback POST routes:
`/internal/tools/search_catalog` and `/internal/tools/get_product_route` only.
The gateway owns and emits candidate/route events from service DTOs. A bridge
cannot submit arbitrary cards/map actions. Candidate expiry is 60 seconds; an
ambiguous search requires a later shopper turn or explicit selection.

Foundation contract snapshot source: TASK-0001's 2026-10-13 local handoff,
`data/contracts/live.schema.json` and `private.schema.json`; hashes are recorded
under `agent/tests/contracts/provenance.json`. Final foundation/Grok acceptance
and a clean rebase remain integration gates.
