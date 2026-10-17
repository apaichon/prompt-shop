// Package voice owns admission, ephemeral turn state and private read-only tools.
package voice

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"regexp"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

var entityID = regexp.MustCompile(`^[a-z0-9-]{1,64}$`)

var ErrStale = errors.New("STALE_SELECTION")
var ErrLimit = errors.New("RATE_LIMITED")
var ErrClassification = errors.New("CLASSIFICATION_REQUIRED")

type Location struct {
	ID    string `json:"id"`
	Label string `json:"label"`
}
type Product struct {
	ID             string   `json:"id"`
	Name           string   `json:"name"`
	Category       string   `json:"category"`
	Aisle          Location `json:"aisle"`
	Shelf          Location `json:"shelf"`
	RouteAvailable bool     `json:"route_available"`
}
type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}
type SearchResult struct {
	SearchID       string    `json:"search_id"`
	CatalogVersion int64     `json:"catalog_version"`
	Candidates     []Product `json:"candidates"`
	Ambiguous      bool      `json:"ambiguous"`
}
type RouteResult struct {
	Product        Product  `json:"product"`
	CatalogVersion int64    `json:"catalog_version"`
	MapVersion     int64    `json:"map_version"`
	OriginNodeID   string   `json:"origin_node_id"`
	NodeIDs        []string `json:"node_ids"`
	Points         []Point  `json:"points"`
	Steps          []string `json:"steps"`
	DistanceUnits  float64  `json:"distance_units"`
}

// Implement with TASK-0002 services. Implementations must use a coherent DB
// snapshot, published-only reads, and a database sub-deadline of 750 ms.
type Catalog interface {
	Search(context.Context, string, string) (SearchResult, error)
	Route(context.Context, string) (RouteResult, error)
}
type Call struct {
	SessionID               string          `json:"session_id"`
	TurnID                  Epoch           `json:"turn_id"`
	CallID                  string          `json:"call_id"`
	ClassificationAttemptID string          `json:"classification_attempt_id"`
	Args                    json.RawMessage `json:"args"`
}
type Event map[string]any

type Session struct {
	mu                          sync.Mutex
	ID, Language, capability    string
	turn                        Epoch
	ctx                         context.Context
	cancel                      context.CancelFunc
	turnCtx                     context.Context
	cancelTurn                  context.CancelFunc
	closed                      bool
	failed                      bool
	classification              string
	searches, routes, summaries int
	calls                       map[string]bool
	candidates                  map[string]bool
	searchID                    string
	searchTurn                  Epoch
	searchExpiry                time.Time
	ambiguous                   bool
	history                     []summaryRecord
	historyTruncated            bool
	audioAllowed                bool
	emit                        func(Event) error
}

func randomToken() string {
	var b [32]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic("cryptographic random source unavailable")
	}
	return base64.RawURLEncoding.EncodeToString(b[:])
}
func tokenHash(raw string) string { b := sha256.Sum256([]byte(raw)); return hex.EncodeToString(b[:]) }
func NewSession(parent context.Context, id, language string, emit func(Event) error) *Session {
	ctx, cancel := context.WithCancel(parent)
	tctx, tcancel := context.WithCancel(ctx)
	return &Session{ID: id, Language: language, capability: randomToken(), ctx: ctx, cancel: cancel, turnCtx: tctx, cancelTurn: tcancel,
		calls: map[string]bool{}, candidates: map[string]bool{}, emit: emit}
}
func (s *Session) BeginTurn() Epoch {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.cancelTurn()
	s.turnCtx, s.cancelTurn = context.WithCancel(s.ctx)
	s.turn++
	s.classification = ""
	s.searches = 0
	s.routes = 0
	s.summaries = 0
	s.calls = map[string]bool{}
	s.audioAllowed = false
	s.failed = false
	return s.turn
}
func (s *Session) Turn() Epoch { s.mu.Lock(); defer s.mu.Unlock(); return s.turn }
func (s *Session) AudioAllowed(turn Epoch) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return !s.closed && !s.failed && s.turn == turn && s.audioAllowed
}

// FailTurn seals late tools/audio while retaining the healthy connection.
func (s *Session) FailTurn(turn Epoch) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.turn != turn || s.failed {
		return false
	}
	s.failed = true
	s.audioAllowed = false
	s.cancelTurn()
	return true
}
func (s *Session) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.closed = true
	s.capability = ""
	s.candidates = nil
	s.history = nil
	s.cancelTurn()
	s.cancel()
}
func (s *Session) Authenticate(capability string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return !s.closed && len(capability) >= 32 && subtle.ConstantTimeCompare([]byte(s.capability), []byte(capability)) == 1
}
func (s *Session) RegisterClassification(turn Epoch, attempt, responseMode string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.failed || s.turn != turn || turn == 0 || s.classification != "" || len(attempt) < 16 || len(attempt) > 128 {
		return ErrStale
	}
	if responseMode == "" {
		responseMode = "catalog"
	}
	if responseMode != "catalog" && responseMode != "conversation" {
		return errors.New("INVALID_REQUEST")
	}
	s.classification = attempt
	s.audioAllowed = responseMode == "conversation"
	return nil
}

// AllowResponse releases a clarification or failure reply from the authenticated
// ADK bridge only after classification. It cannot revive failed or stale turns.
func (s *Session) AllowResponse(turn Epoch, attempt string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.failed || turn == 0 || s.turn != turn || s.classification == "" || s.classification != attempt {
		return ErrStale
	}
	s.audioAllowed = true
	return nil
}

func (s *Session) beginCall(call Call, name string) (context.Context, context.CancelFunc, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.failed || call.SessionID != s.ID || call.TurnID != s.turn || s.turn == 0 || len(call.CallID) < 16 || len(call.CallID) > 128 || s.calls[call.CallID] {
		return nil, nil, ErrStale
	}
	if s.classification == "" || call.ClassificationAttemptID != s.classification {
		return nil, nil, ErrClassification
	}
	switch name {
	case "search_catalog":
		if s.searches >= 2 {
			return nil, nil, ErrLimit
		}
		s.searches++
	case "get_conversation_summary":
		if s.summaries >= 1 {
			return nil, nil, ErrLimit
		}
		s.summaries++
	case "get_product_route":
		if s.routes >= 1 {
			return nil, nil, ErrLimit
		}
		s.routes++
	default:
		return nil, nil, errors.New("INVALID_REQUEST")
	}
	// Moving from chat into a catalog operation restores the tool-result gate.
	s.audioAllowed = false
	s.calls[call.CallID] = true
	ctx, cancel := context.WithTimeout(s.turnCtx, 1500*time.Millisecond)
	return ctx, cancel, nil
}
func (s *Session) Search(call Call, catalog Catalog) (SearchResult, error) {
	var args struct {
		Query string `json:"query"`
	}
	if strictJSON(call.Args, &args) != nil || !validText(args.Query, 200) {
		return SearchResult{}, errors.New("INVALID_REQUEST")
	}
	ctx, cancel, err := s.beginCall(call, "search_catalog")
	if err != nil {
		return SearchResult{}, err
	}
	defer cancel()
	result, err := catalog.Search(ctx, args.Query, s.Language)
	if err != nil {
		return SearchResult{}, err
	}
	if ctx.Err() != nil {
		return SearchResult{}, ctx.Err()
	}
	if len(result.Candidates) > 3 {
		return SearchResult{}, errors.New("invalid catalog result")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.failed || s.turn != call.TurnID {
		return SearchResult{}, ErrStale
	}
	s.candidates = map[string]bool{}
	for _, p := range result.Candidates {
		if p.ID == "" || s.candidates[p.ID] {
			return SearchResult{}, errors.New("invalid catalog result")
		}
		s.candidates[p.ID] = true
	}
	result.SearchID = randomToken()
	result.Ambiguous = len(result.Candidates) > 1
	if result.Candidates == nil {
		result.Candidates = []Product{}
	}
	s.searchID = result.SearchID
	s.searchTurn = s.turn
	s.searchExpiry = time.Now().Add(time.Minute)
	s.ambiguous = result.Ambiguous
	s.audioAllowed = result.Ambiguous || len(result.Candidates) == 0
	s.rememberSearch(args.Query, result)
	if s.emit != nil {
		if err := s.emit(Event{"type": "candidates", "session_id": s.ID, "turn_id": s.turn, "search_id": result.SearchID, "catalog_version": result.CatalogVersion, "candidates": result.Candidates}); err != nil {
			return SearchResult{}, err
		}
	}
	if err := s.emitSummary(false); err != nil {
		return SearchResult{}, err
	}
	return result, nil
}
func (s *Session) Route(call Call, catalog Catalog) (RouteResult, error) {
	var args struct {
		ProductID string `json:"product_id"`
		SearchID  string `json:"search_id"`
	}
	if strictJSON(call.Args, &args) != nil || !entityID.MatchString(args.ProductID) || !validText(args.SearchID, 128) {
		return RouteResult{}, errors.New("INVALID_REQUEST")
	}
	ctx, cancel, err := s.beginCall(call, "get_product_route")
	if err != nil {
		return RouteResult{}, err
	}
	defer cancel()
	return s.route(ctx, call.TurnID, args.ProductID, args.SearchID, catalog)
}
func (s *Session) route(ctx context.Context, turn Epoch, productID, searchID string, catalog Catalog) (RouteResult, error) {
	s.mu.Lock()
	valid := !s.closed && !s.failed && s.turn == turn && s.searchID == searchID && s.candidates[productID] && time.Now().Before(s.searchExpiry) && (!s.ambiguous || turn > s.searchTurn)
	s.mu.Unlock()
	if !valid {
		return RouteResult{}, ErrStale
	}
	result, err := catalog.Route(ctx, productID)
	if err != nil {
		return RouteResult{}, err
	}
	if ctx.Err() != nil {
		return RouteResult{}, ctx.Err()
	}
	if result.Product.ID != productID || result.OriginNodeID != "entrance" || len(result.NodeIDs) == 0 || len(result.Points) != len(result.NodeIDs) {
		return RouteResult{}, errors.New("invalid route result")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.failed || s.turn != turn || s.searchID != searchID || time.Now().After(s.searchExpiry) {
		return RouteResult{}, ErrStale
	}
	s.audioAllowed = true
	s.rememberRoute(searchID, result)
	if s.emit != nil {
		data, _ := json.Marshal(result)
		event := Event{}
		_ = json.Unmarshal(data, &event)
		event["type"] = "route"
		event["session_id"] = s.ID
		event["turn_id"] = turn
		event["search_id"] = searchID
		if err := s.emit(event); err != nil {
			return RouteResult{}, err
		}
	}
	if err := s.emitSummary(false); err != nil {
		return RouteResult{}, err
	}
	return result, nil
}

// Select is an explicit shopper action; it deliberately has no Laya prerequisite.
func (s *Session) Select(ctx context.Context, turn Epoch, productID, searchID string, catalog Catalog) (RouteResult, error) {
	ctx, cancel := context.WithTimeout(ctx, 1500*time.Millisecond)
	defer cancel()
	return s.route(ctx, turn, productID, searchID, catalog)
}
func strictJSON(raw []byte, dst any) error {
	d := json.NewDecoder(strings.NewReader(string(raw)))
	d.DisallowUnknownFields()
	if err := d.Decode(dst); err != nil {
		return err
	}
	if d.Decode(&struct{}{}) != io.EOF {
		return errors.New("trailing JSON")
	}
	return nil
}
func validText(value string, max int) bool {
	return utf8.ValidString(value) && strings.TrimSpace(value) != "" && utf8.RuneCountInString(value) <= max
}
