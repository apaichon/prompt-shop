package voice

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"log/slog"
	"math"
	"net"
	"net/http"
	"net/url"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/fasthttp/websocket"
	"github.com/gofiber/fiber/v2"
	"github.com/valyala/fasthttp"
)

const sessionLifetime = 10 * time.Minute
const maxSessionAudioBytes = 20 << 20

const Protocol = "prompt-shop.voice.v1"
const ticketCookie = "__Host-voice-ticket"

type GatewayConfig struct {
	Origin, BridgeSecret string
	Enabled              bool
	AllowLocalHTTP       bool
	SessionValidator     func(*fiber.Ctx) func() bool
}
type Gateway struct {
	config   GatewayConfig
	tickets  TicketStore
	catalog  Catalog
	Registry *Registry
	active   atomic.Int32
	rateMu   sync.Mutex
	rates    map[string]rateEntry
}
type rateEntry struct {
	tokens float64
	at     time.Time
}

func NewGateway(config GatewayConfig, tickets TicketStore, catalog Catalog) (*Gateway, error) {
	u, err := url.Parse(config.Origin)
	localHTTP := false
	if err == nil && config.AllowLocalHTTP && os.Getenv("K_SERVICE") == "" && u.Scheme == "http" {
		ip := net.ParseIP(u.Hostname())
		localHTTP = u.Hostname() == "localhost" || ip != nil && ip.IsLoopback()
	}
	if err != nil || (u.Scheme != "https" && !localHTTP) || u.Host == "" || u.User != nil || u.Path != "" || u.RawQuery != "" || u.Fragment != "" || len(config.BridgeSecret) < 32 || tickets == nil || catalog == nil {
		return nil, errors.New("invalid voice configuration")
	}
	return &Gateway{config: config, tickets: tickets, catalog: catalog, Registry: NewRegistry(), rates: map[string]rateEntry{}}, nil
}
func (g *Gateway) Register(router fiber.Router) {
	router.Post("/api/voice/sessions", g.issue)
	router.Get("/ws/voice", g.upgrade)
}
func (g *Gateway) allow(ip string) bool {
	g.rateMu.Lock()
	defer g.rateMu.Unlock()
	now := time.Now()
	for key, v := range g.rates {
		if now.Sub(v.at) > time.Minute {
			delete(g.rates, key)
		}
	}
	v, ok := g.rates[ip]
	if !ok {
		if len(g.rates) >= 1024 {
			return false
		}
		v = rateEntry{2, now}
	}
	v.tokens = math.Min(2, v.tokens+now.Sub(v.at).Seconds()/10)
	v.at = now
	allowed := v.tokens >= 1
	if allowed {
		v.tokens--
	}
	g.rates[ip] = v
	return allowed
}
func (g *Gateway) issue(c *fiber.Ctx) error {
	c.Set("Cache-Control", "no-store")
	if c.Get("Origin") != g.config.Origin {
		return publicError(c, 403, "FORBIDDEN")
	}
	if !g.config.Enabled {
		return publicError(c, 503, "DEPENDENCY_UNAVAILABLE")
	}
	if !g.allow(c.IP()) {
		c.Set("Retry-After", "10")
		return publicError(c, 429, "RATE_LIMITED")
	}
	if len(c.Body()) > 1024 || c.Get("Content-Type") != "application/json" {
		return publicError(c, 400, "INVALID_REQUEST")
	}
	var body struct {
		Language string `json:"language"`
	}
	if strictJSON(c.Body(), &body) != nil || body.Language != "en-US" {
		return publicError(c, 400, "LANGUAGE_DISABLED")
	}
	if g.active.Load() >= 4 {
		return publicError(c, 429, "SESSION_LIMIT")
	}
	raw := randomToken()
	t := Ticket{randomToken(), body.Language, time.Now().UTC().Add(30 * time.Second)}
	previous := ""
	if old := c.Cookies(ticketCookie); old != "" {
		previous = tokenHash(old)
	}
	if err := g.tickets.Issue(c.UserContext(), tokenHash(raw), previous, t); err != nil {
		return publicError(c, 503, "DEPENDENCY_UNAVAILABLE")
	}
	c.Cookie(&fiber.Cookie{Name: ticketCookie, Value: raw, Secure: true, HTTPOnly: true, SameSite: "Strict", Path: "/", MaxAge: 30, Expires: t.ExpiresAt})
	return c.Status(201).JSON(Event{"session_id": t.SessionID, "ticket_expires_at": t.ExpiresAt, "ws_path": "/ws/voice"})
}
func publicError(c *fiber.Ctx, status int, code string) error {
	return c.Status(status).JSON(Event{"error": Event{"code": code, "message": "Voice unavailable; retry or use typed search.", "retryable": status >= 500}, "request_id": c.GetRespHeader("X-Request-ID")})
}
func (g *Gateway) upgrade(c *fiber.Ctx) error {
	var authorized func() bool
	if g.config.SessionValidator != nil {
		authorized = g.config.SessionValidator(c)
		if authorized == nil || !authorized() {
			return publicError(c, 401, "AUTH_REQUIRED")
		}
	}
	if !g.config.Enabled {
		return publicError(c, 503, "DEPENDENCY_UNAVAILABLE")
	}
	if c.Get("Origin") != g.config.Origin {
		return publicError(c, 403, "FORBIDDEN")
	}
	if len(c.Context().URI().QueryString()) != 0 || c.Get("Sec-WebSocket-Protocol") != Protocol || !websocket.FastHTTPIsWebSocketUpgrade(c.Context()) {
		return publicError(c, 400, "INVALID_REQUEST")
	}
	raw := c.Cookies(ticketCookie)
	if len(raw) != 43 {
		return publicError(c, 401, "SESSION_TICKET_INVALID")
	}
	if g.active.Add(1) > 4 {
		g.active.Add(-1)
		return publicError(c, 429, "SESSION_LIMIT")
	}
	t, err := g.tickets.Consume(c.UserContext(), tokenHash(raw))
	if err != nil {
		g.active.Add(-1)
		return publicError(c, 401, "SESSION_TICKET_INVALID")
	}
	if t.Language != "en-US" {
		g.active.Add(-1)
		return publicError(c, 401, "SESSION_TICKET_INVALID")
	}
	c.Cookie(&fiber.Cookie{Name: ticketCookie, Value: "", Secure: true, HTTPOnly: true, SameSite: "Strict", Path: "/", MaxAge: -1})
	upgrader := websocket.FastHTTPUpgrader{Subprotocols: []string{Protocol}, CheckOrigin: func(ctx *fasthttp.RequestCtx) bool {
		return string(ctx.Request.Header.Peek("Origin")) == g.config.Origin
	}}
	err = upgrader.Upgrade(c.Context(), func(client *websocket.Conn) { defer g.active.Add(-1); g.relay(client, t, authorized) })
	if err != nil {
		g.active.Add(-1)
		return publicError(c, 400, "INVALID_REQUEST")
	}
	return nil
}

type frame struct {
	kind int
	data []byte
	turn Epoch
}
type outbox struct {
	mu     sync.Mutex
	frames []frame
	bytes  int
	wake   chan struct{}
}

func newOutbox() *outbox { return &outbox{wake: make(chan struct{}, 1)} }
func (q *outbox) push(f frame) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	audio := 0
	if f.kind == websocket.BinaryMessage {
		audio = len(f.data)
	}
	if len(q.frames) >= 64 || q.bytes+audio > 48000 {
		return errors.New("CLIENT_TOO_SLOW")
	}
	q.frames = append(q.frames, f)
	q.bytes += audio
	select {
	case q.wake <- struct{}{}:
	default:
	}
	return nil
}
func (q *outbox) pop(ctx context.Context) (frame, error) {
	for {
		q.mu.Lock()
		if len(q.frames) > 0 {
			f := q.frames[0]
			q.frames[0] = frame{}
			q.frames = q.frames[1:]
			if f.kind == websocket.BinaryMessage {
				q.bytes -= len(f.data)
			}
			q.mu.Unlock()
			return f, nil
		}
		q.mu.Unlock()
		select {
		case <-ctx.Done():
			return frame{}, ctx.Err()
		case <-q.wake:
		}
	}
}
func (q *outbox) flush() { q.mu.Lock(); q.frames = nil; q.bytes = 0; q.mu.Unlock() }

func (g *Gateway) relay(client *websocket.Conn, t Ticket, authorized func() bool) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	defer client.Close()
	q := newOutbox()
	emit := func(event Event) error {
		raw, err := json.Marshal(event)
		if err != nil {
			return err
		}
		turn, _ := event["turn_id"].(Epoch)
		err = q.push(frame{websocket.TextMessage, raw, turn})
		if err != nil {
			cancel()
		}
		return err
	}
	s := NewSession(ctx, t.SessionID, t.Language, emit)
	g.Registry.add(s)
	defer g.Registry.remove(s.ID)
	setupCtx, setupCancel := context.WithTimeout(ctx, 30*time.Second)
	defer setupCancel()
	dialer := websocket.Dialer{HandshakeTimeout: 30 * time.Second, ReadBufferSize: 4096, WriteBufferSize: 4096}
	bridge, resp, err := dialer.DialContext(setupCtx, "ws://127.0.0.1:8001/live", http.Header{"Authorization": []string{"Bearer " + g.config.BridgeSecret}})
	if resp != nil && resp.Body != nil {
		resp.Body.Close()
	}
	if err != nil {
		_ = client.WriteJSON(Event{"type": "error", "session_id": s.ID, "code": "DEPENDENCY_UNAVAILABLE", "message": "Voice could not start; retry or use typed search.", "retryable": true})
		return
	}
	defer bridge.Close()
	var bridgeMu sync.Mutex
	bridgeSend := func(kind int, data []byte) error {
		bridgeMu.Lock()
		defer bridgeMu.Unlock()
		_ = bridge.SetWriteDeadline(time.Now().Add(time.Second))
		return bridge.WriteMessage(kind, data)
	}
	bridgeEvent := func(event Event) error {
		event["session_id"] = s.ID
		raw, _ := json.Marshal(event)
		return bridgeSend(websocket.TextMessage, raw)
	}
	if bridgeEvent(Event{"type": "setup", "language": s.Language, "turn_id": Epoch(0), "tool_capability": s.capability}) != nil {
		return
	}
	var ready atomic.Bool
	var activity, readyAt, pong atomic.Int64
	activity.Store(time.Now().UnixNano())
	pong.Store(time.Now().UnixNano())
	client.SetReadLimit(6400)
	bridge.SetReadLimit(65536)
	client.SetPongHandler(func(string) error { pong.Store(time.Now().UnixNano()); return nil })
	// All public writes, including RFC ping frames, run through one writer.
	var wg sync.WaitGroup
	endings := make(chan error, 4)
	start := func(fn func() error) {
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer cancel()
			err := fn()
			select {
			case endings <- err:
			default:
			}
		}()
	}
	start(func() error {
		for {
			f, err := q.pop(ctx)
			if err != nil {
				return err
			}
			if f.turn != 0 && f.turn != s.Turn() {
				continue
			}
			_ = client.SetWriteDeadline(time.Now().Add(time.Second))
			if err = client.WriteMessage(f.kind, f.data); err != nil {
				return err
			}
		}
	})
	start(func() error {
		audioTurn := Epoch(0)
		for {
			kind, data, err := bridge.ReadMessage()
			if err != nil {
				return err
			}
			if kind == websocket.BinaryMessage {
				if audioTurn == 0 || !s.AudioAllowed(audioTurn) {
					continue
				}
				if len(data) == 0 || len(data) > 16384 || len(data)%2 != 0 {
					return errors.New("INVALID_AUDIO")
				}
				if err = q.push(frame{kind, data, audioTurn}); err != nil {
					return err
				}
				continue
			}
			if kind != websocket.TextMessage {
				return errors.New("INVALID_REQUEST")
			}
			var event map[string]json.RawMessage
			if json.Unmarshal(data, &event) != nil {
				return errors.New("INVALID_REQUEST")
			}
			var sid, typ string
			_ = json.Unmarshal(event["session_id"], &sid)
			_ = json.Unmarshal(event["type"], &typ)
			if sid != s.ID {
				return ErrStale
			}
			var turn Epoch
			_ = json.Unmarshal(event["turn_id"], &turn)
			switch typ {
			case "provider_ready":
				if ready.Swap(true) {
					return errors.New("duplicate ready")
				}
				now := time.Now()
				readyAt.Store(now.UnixNano())
				activity.Store(now.UnixNano())
				if err = emit(Event{"type": "ready", "session_id": s.ID, "expires_at": now.Add(sessionLifetime).UTC(), "input_rate": 16000, "output_rate": 24000}); err != nil {
					return err
				}
			case "classification_completed":
				var attempt string
				_ = json.Unmarshal(event["classification_attempt_id"], &attempt)
				var result struct {
					Intent    *string `json:"intent"`
					Abstained bool    `json:"abstained"`
				}
				if json.Unmarshal(event["result"], &result) != nil {
					return errors.New("INVALID_REQUEST")
				}
				var responseMode string
				if raw, present := event["response_mode"]; present && json.Unmarshal(raw, &responseMode) != nil {
					return errors.New("INVALID_REQUEST")
				}
				if s.RegisterClassification(turn, attempt, responseMode) != nil {
					continue
				}
				if err = bridgeEvent(Event{"type": "classification_registered", "turn_id": turn, "classification_attempt_id": attempt}); err != nil {
					return err
				}
			case "audio_start":
				if turn != s.Turn() || !s.AudioAllowed(turn) {
					audioTurn = 0
					continue
				}
				audioTurn = turn
				if err = q.push(frame{kind, data, turn}); err != nil {
					return err
				}
			case "audio_end", "turn_complete", "input_transcript", "output_transcript", "interrupted":
				if turn != s.Turn() {
					continue
				}
				if typ == "interrupted" {
					q.flush()
					audioTurn = 0
				}
				if typ == "output_transcript" && !s.AudioAllowed(turn) {
					continue
				}
				if err = q.push(frame{kind, data, turn}); err != nil {
					return err
				}
			case "error":
				var code string
				_ = json.Unmarshal(event["code"], &code)
				if code == "TURN_TIMEOUT" {
					if !s.FailTurn(turn) {
						continue
					}
					q.flush()
					audioTurn = 0
					if err = emit(Event{"type": "error", "session_id": s.ID, "turn_id": turn,
						"code": "TURN_TIMEOUT", "message": "That reply timed out. Please ask again.", "retryable": true}); err != nil {
						return err
					}
					continue
				}
				_ = emit(Event{"type": "error", "session_id": s.ID, "code": "DEPENDENCY_UNAVAILABLE", "message": "Voice ended; retry or use typed search.", "retryable": true})
				return errors.New("provider ended")
			default:
				return errors.New("INVALID_REQUEST")
			}
		}
	})
	start(func() error {
		tokens := float64(64 << 10)
		last := time.Now()
		total := 0
		controls := 0
		window := time.Now()
		input := inputActivity{}
		begin := func() error {
			turn := s.BeginTurn()
			q.flush()
			if err := emit(Event{"type": "interrupted", "session_id": s.ID, "turn_id": turn, "generation_id": generationID(turn)}); err != nil {
				return err
			}
			return bridgeEvent(Event{"type": "begin_turn", "turn_id": turn})
		}
		for {
			kind, data, err := client.ReadMessage()
			if err != nil {
				return err
			}
			now := time.Now()
			if kind == websocket.BinaryMessage {
				if !ready.Load() || len(data) == 0 || len(data) > 6400 || len(data)%2 != 0 {
					return errors.New("INVALID_AUDIO")
				}
				tokens = math.Min(64<<10, tokens+now.Sub(last).Seconds()*(40<<10))
				last = now
				tokens -= float64(len(data))
				total += len(data)
				if tokens < 0 || total > maxSessionAudioBytes {
					return ErrLimit
				}
				started, ended, frames := input.push(data)
				if started {
					if err = begin(); err != nil {
						return err
					}
				}
				if len(frames) > 0 && voiced(data) {
					activity.Store(now.UnixNano())
				}
				for _, pcm := range frames {
					if err = bridgeSend(kind, pcm); err != nil {
						return err
					}
				}
				if ended {
					if err = bridgeEvent(Event{"type": "activity_end", "turn_id": s.Turn()}); err != nil {
						return err
					}
				}
				continue
			}
			if kind != websocket.TextMessage || len(data) > 4096 {
				return errors.New("INVALID_REQUEST")
			}
			if now.Sub(window) >= time.Second {
				window = now
				controls = 0
			}
			controls++
			if controls > 10 {
				return ErrLimit
			}
			var event struct {
				Type      string `json:"type"`
				SessionID string `json:"session_id"`
				Text      string `json:"text,omitempty"`
				SearchID  string `json:"search_id,omitempty"`
				ProductID string `json:"product_id,omitempty"`
			}
			if strictJSON(data, &event) != nil || event.SessionID != s.ID {
				return errors.New("INVALID_REQUEST")
			}
			switch event.Type {
			case "stop":
				if event.Text != "" || event.SearchID != "" || event.ProductID != "" {
					return errors.New("INVALID_REQUEST")
				}
				return nil
			case "ping":
				if event.Text != "" || event.SearchID != "" || event.ProductID != "" {
					return errors.New("INVALID_REQUEST")
				}
				if err = emit(Event{"type": "pong", "session_id": s.ID}); err != nil {
					return err
				}
			case "text":
				if !ready.Load() || !validText(event.Text, 200) || event.SearchID != "" || event.ProductID != "" {
					return errors.New("INVALID_REQUEST")
				}
				activity.Store(now.UnixNano())
				if err = begin(); err != nil {
					return err
				}
				input.reset()
				if err = bridgeEvent(Event{"type": "text", "turn_id": s.Turn(), "text": event.Text}); err != nil {
					return err
				}
			case "select":
				if !ready.Load() || event.Text != "" || !entityID.MatchString(event.ProductID) || !validText(event.SearchID, 128) {
					return errors.New("INVALID_REQUEST")
				}
				activity.Store(now.UnixNano())
				if err = begin(); err != nil {
					return err
				}
				input.reset()
				result, e := s.Select(ctx, s.Turn(), event.ProductID, event.SearchID, g.catalog)
				if e != nil {
					_ = emit(Event{"type": "error", "session_id": s.ID, "code": "STALE_SELECTION", "message": "Select from a fresh search.", "retryable": true})
					continue
				}
				if err = bridgeEvent(Event{"type": "text", "turn_id": s.Turn(), "text": "I selected product " + result.Product.ID + ". Please confirm its directions using the route tool."}); err != nil {
					return err
				}
			default:
				return errors.New("INVALID_REQUEST")
			}
		}
	})
	start(func() error {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		startTime := time.Now()
		nextPing := time.Now().Add(20 * time.Second)
		pendingPing := time.Time{}
		for {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case now := <-ticker.C:
				if authorized != nil && !authorized() {
					return errors.New("SESSION_EXPIRED")
				}
				if !ready.Load() && now.Sub(startTime) >= 30*time.Second {
					return errors.New("SETUP_TIMEOUT")
				}
				if ready.Load() && (now.Sub(time.Unix(0, readyAt.Load())) >= sessionLifetime || now.Sub(time.Unix(0, activity.Load())) >= 60*time.Second) {
					return errors.New("SESSION_EXPIRED")
				}
				if !pendingPing.IsZero() {
					if time.Unix(0, pong.Load()).After(pendingPing) {
						pendingPing = time.Time{}
					} else if now.Sub(pendingPing) > 10*time.Second {
						return errors.New("transport timeout")
					}
				}
				if now.After(nextPing) {
					if err := q.push(frame{kind: websocket.PingMessage}); err != nil {
						return err
					}
					pendingPing = now
					nextPing = now.Add(20 * time.Second)
				}
			}
		}
	})
	<-ctx.Done()
	_ = client.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(closeCode(endings), "Voice ended; start a fresh session or use typed search."), time.Now().Add(time.Second))
	s.Close()
	_ = client.Close()
	_ = bridge.Close()
	wg.Wait()
}

// Bounded energy detector defines meaningful activity; pings and silent PCM do
// not refresh idle time. Device qualification must verify this fixed threshold.
func voiced(pcm []byte) bool {
	if len(pcm) < 2 {
		return false
	}
	sum := float64(0)
	for i := 0; i+1 < len(pcm); i += 2 {
		v := float64(int16(binary.LittleEndian.Uint16(pcm[i:])))
		sum += v * v
	}
	return math.Sqrt(sum/float64(len(pcm)/2)) >= 500
}

func closeCode(endings <-chan error) int {
	select {
	case err := <-endings:
		slog.Info("voice_session_end", "reason", sessionEndReason(err))
		if err == nil {
			return websocket.CloseNormalClosure
		}
		switch err.Error() {
		case "INVALID_AUDIO":
			return websocket.CloseUnsupportedData
		case "MESSAGE_TOO_LARGE":
			return websocket.CloseMessageTooBig
		case "RATE_LIMITED", "INVALID_REQUEST":
			return websocket.ClosePolicyViolation
		case "SESSION_EXPIRED":
			return websocket.CloseNormalClosure
		default:
			return websocket.CloseInternalServerErr
		}
	default:
		return websocket.CloseInternalServerErr
	}
}

// Do not log err.Error(): provider/transport errors may contain sensitive data.
func sessionEndReason(err error) string {
	if err == nil {
		return "client_stop"
	}
	switch err.Error() {
	case "INVALID_AUDIO", "INVALID_REQUEST", "RATE_LIMITED", "SETUP_TIMEOUT", "SESSION_EXPIRED", "CLIENT_TOO_SLOW":
		return err.Error()
	case "provider ended":
		return "provider_ended"
	case "transport timeout":
		return "transport_timeout"
	}
	return "transport_failure"
}
