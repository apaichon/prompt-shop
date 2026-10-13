package voice

import (
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/fasthttp/websocket"
	"github.com/gofiber/fiber/v2"
)

func TestGatewayBridgeACKAndVerifiedEvents(t *testing.T) {
	tickets := &memoryTickets{}
	g, err := NewGateway(GatewayConfig{Origin: "https://shop.example", BridgeSecret: strings.Repeat("s", 43), Enabled: true}, tickets, &fixtureCatalog{products: []Product{{ID: "milk"}, {ID: "oat"}}})
	if err != nil {
		t.Fatal(err)
	}
	listener, err := net.Listen("tcp", "127.0.0.1:8001")
	if err != nil {
		t.Fatal("private bridge port occupied: ", err)
	}
	bridgeErrors := make(chan error, 1)
	bridge := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer "+strings.Repeat("s", 43) {
			bridgeErrors <- fmt.Errorf("missing bridge authentication")
			return
		}
		conn, e := (&websocket.Upgrader{}).Upgrade(w, r, nil)
		if e != nil {
			bridgeErrors <- e
			return
		}
		defer conn.Close()
		var setup map[string]any
		if e = conn.ReadJSON(&setup); e != nil {
			bridgeErrors <- e
			return
		}
		sid := setup["session_id"].(string)
		capability := setup["tool_capability"].(string)
		_ = conn.WriteJSON(Event{"type": "provider_ready", "session_id": sid})
		for {
			var event map[string]any
			if e = conn.ReadJSON(&event); e != nil {
				return
			}
			if event["type"] == "text" {
				_ = conn.WriteJSON(Event{"type": "classification_completed", "session_id": sid, "turn_id": event["turn_id"], "classification_attempt_id": "classification-attempt-0001", "result": Event{"intent": "find_item", "abstained": false}})
			}
			if event["type"] == "classification_registered" {
				call := Call{SessionID: sid, TurnID: parseEpoch(event["turn_id"].(string)), CallID: randomToken(), ClassificationAttemptID: "classification-attempt-0001", Args: json.RawMessage(`{"query":"milk"}`)}
				raw, _ := json.Marshal(call)
				req := httptest.NewRequest("POST", "/internal/tools/search_catalog", strings.NewReader(string(raw)))
				req.Header.Set("Authorization", "Bearer "+capability)
				req.Header.Set("Content-Type", "application/json")
				result := httptest.NewRecorder()
				PrivateHandler(g.Registry, g.catalog).ServeHTTP(result, req)
				if result.Code != 200 {
					bridgeErrors <- fmt.Errorf("callback before ACK state: %d", result.Code)
					return
				}
				_ = conn.WriteJSON(Event{"type": "audio_start", "session_id": sid, "turn_id": event["turn_id"], "generation_id": "generation-1"})
				_ = conn.WriteMessage(websocket.BinaryMessage, []byte{1, 0, 2, 0})
			}
		}
	}))
	bridge.Listener.Close()
	bridge.Listener = listener
	bridge.Start()
	defer bridge.Close()
	app := fiber.New(fiber.Config{DisableStartupMessage: true})
	g.Register(app)
	public, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan struct{})
	go func() { defer close(done); _ = app.Listener(public) }()
	defer func() { _ = app.Shutdown(); <-done }()
	req := httptest.NewRequest("POST", "/api/voice/sessions", strings.NewReader(`{"language":"en-US"}`))
	req.Header.Set("Origin", "https://shop.example")
	req.Header.Set("Content-Type", "application/json")
	resp, err := app.Test(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	cookie := resp.Cookies()[0]
	dialer := websocket.Dialer{Subprotocols: []string{Protocol}}
	conn, _, err := dialer.Dial("ws://"+public.Addr().String()+"/ws/voice", http.Header{"Origin": []string{"https://shop.example"}, "Cookie": []string{cookie.Name + "=" + cookie.Value}})
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	_ = conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	var ready map[string]any
	if err = conn.ReadJSON(&ready); err != nil {
		t.Fatal(err)
	}
	if ready["type"] != "ready" {
		t.Fatal(ready)
	}
	sid := ready["session_id"].(string)
	if err = conn.WriteJSON(Event{"type": "text", "session_id": sid, "text": "milk"}); err != nil {
		t.Fatal(err)
	}
	candidates, audioStart, audio := false, false, false
	for !audio {
		kind, data, e := conn.ReadMessage()
		if e != nil {
			select {
			case cause := <-bridgeErrors:
				t.Fatal(cause)
			default:
				t.Fatal(e)
			}
		}
		if kind == websocket.BinaryMessage {
			if !audioStart {
				t.Fatal("audio lacked generation header")
			}
			audio = true
			continue
		}
		var event map[string]any
		_ = json.Unmarshal(data, &event)
		switch event["type"] {
		case "candidates":
			candidates = true
		case "audio_start":
			audioStart = true
		}
	}
	if !candidates {
		t.Fatal("audio without verified candidate event")
	}
	// Malformed PCM must produce an explicit unsupported-data close.
	_ = conn.WriteMessage(websocket.BinaryMessage, []byte{1})
	_, _, err = conn.ReadMessage()
	if !websocket.IsCloseError(err, websocket.CloseUnsupportedData) {
		t.Fatalf("invalid PCM close: %v", err)
	}
	conn.Close()
	deadline := time.Now().Add(3 * time.Second)
	for g.active.Load() != 0 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if g.active.Load() != 0 || g.Registry.get(sid) != nil {
		t.Fatal("session resources leaked")
	}
}
