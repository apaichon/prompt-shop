package voice

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

type fixtureCatalog struct {
	products []Product
	delay    chan struct{}
}

func (f *fixtureCatalog) Search(ctx context.Context, q, lang string) (SearchResult, error) {
	if f.delay != nil {
		select {
		case <-f.delay:
		case <-ctx.Done():
			return SearchResult{}, ctx.Err()
		}
	}
	return SearchResult{CatalogVersion: 1, Candidates: f.products}, nil
}
func (f *fixtureCatalog) Route(ctx context.Context, id string) (RouteResult, error) {
	return RouteResult{Product: Product{ID: id}, OriginNodeID: "entrance", NodeIDs: []string{"entrance", "shelf"}, Points: []Point{{0, 0}, {1, 1}}, MapVersion: 1}, nil
}
func call(s *Session, args string) Call {
	return Call{SessionID: s.ID, TurnID: s.Turn(), CallID: randomToken(), ClassificationAttemptID: "classification-attempt-0001", Args: json.RawMessage(args)}
}
func classify(t *testing.T, s *Session) {
	t.Helper()
	if err := s.RegisterClassification(s.Turn(), "classification-attempt-0001", "catalog"); err != nil {
		t.Fatal(err)
	}
}
func TestConversationModeResetsBeforeCatalogAndAcrossTurns(t *testing.T) {
	s := NewSession(context.Background(), "session", "en-US", nil)
	defer s.Close()
	turn := s.BeginTurn()
	if err := s.RegisterClassification(turn, "classification-attempt-0001", "arbitrary"); err == nil || s.AudioAllowed(turn) {
		t.Fatal("unknown response mode accepted")
	}
	if err := s.RegisterClassification(turn, "classification-attempt-0001", "conversation"); err != nil || !s.AudioAllowed(turn) {
		t.Fatal("acknowledged conversation did not unlock reply", err)
	}
	catalog := &fixtureCatalog{products: []Product{{ID: "milk"}}}
	result, err := s.Search(call(s, `{"query":"milk"}`), catalog)
	if err != nil || s.AudioAllowed(turn) {
		t.Fatal("unique product bypassed route gate after conversation", err)
	}
	if _, err := s.Route(call(s, `{"product_id":"milk","search_id":"`+result.SearchID+`"}`), catalog); err != nil || !s.AudioAllowed(turn) {
		t.Fatal("verified route did not unlock reply", err)
	}
	next := s.BeginTurn()
	if s.AudioAllowed(next) || s.AudioAllowed(turn) {
		t.Fatal("new turn inherited conversation/route permission")
	}
	// Older peers with no mode fail closed to catalog rather than general chat.
	if err := s.RegisterClassification(next, "classification-attempt-0002", ""); err != nil || s.AudioAllowed(next) {
		t.Fatal("missing response mode unlocked reply", err)
	}
}
func TestToolsRequireClassificationSelectionAndCurrentEpoch(t *testing.T) {
	s := NewSession(context.Background(), "session", "en-US", nil)
	defer s.Close()
	s.BeginTurn()
	catalog := &fixtureCatalog{products: []Product{{ID: "milk"}, {ID: "oat"}}}
	if _, err := s.Search(call(s, `{"query":"milk"}`), catalog); !errors.Is(err, ErrClassification) {
		t.Fatal(err)
	}
	classify(t, s)
	result, err := s.Search(call(s, `{"query":"milk"}`), catalog)
	if err != nil {
		t.Fatal(err)
	}
	args := `{"product_id":"milk","search_id":"` + result.SearchID + `"}`
	if _, err = s.Route(call(s, args), catalog); !errors.Is(err, ErrStale) {
		t.Fatalf("same-turn ambiguity accepted: %v", err)
	}
	s.BeginTurn()
	classify(t, s)
	if _, err = s.Route(call(s, args), catalog); err != nil {
		t.Fatal(err)
	}
	if !s.AudioAllowed(s.Turn()) {
		t.Fatal("grounded route did not unlock audio")
	}
	old := call(s, args)
	s.BeginTurn()
	classify(t, s)
	if _, err = s.Route(old, catalog); !errors.Is(err, ErrStale) {
		t.Fatal("old turn accepted")
	}
	if s.AudioAllowed(s.Turn()) {
		t.Fatal("new turn inherited audio permission")
	}
}
func TestCancelledSearchCannotPublish(t *testing.T) {
	emitted := 0
	s := NewSession(context.Background(), "session", "en-US", func(Event) error { emitted++; return nil })
	defer s.Close()
	s.BeginTurn()
	classify(t, s)
	blocked := make(chan struct{})
	catalog := &fixtureCatalog{delay: blocked}
	done := make(chan error)
	invocation := call(s, `{"query":"milk"}`)
	go func() { _, err := s.Search(invocation, catalog); done <- err }()
	s.BeginTurn()
	close(blocked)
	if err := <-done; err == nil {
		t.Fatal("late result accepted")
	}
	if emitted != 0 {
		t.Fatal("late card emitted")
	}
}
func TestBudgetsDuplicateCallsAndExpiry(t *testing.T) {
	s := NewSession(context.Background(), "session", "en-US", nil)
	defer s.Close()
	s.BeginTurn()
	classify(t, s)
	cat := &fixtureCatalog{products: []Product{{ID: "milk"}}}
	invocation := call(s, `{"query":"milk"}`)
	result, err := s.Search(invocation, cat)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = s.Search(invocation, cat); !errors.Is(err, ErrStale) {
		t.Fatal("duplicate accepted")
	}
	if _, err = s.Search(call(s, `{"query":"milk"}`), cat); err != nil {
		t.Fatal(err)
	}
	if _, err = s.Search(call(s, `{"query":"milk"}`), cat); !errors.Is(err, ErrLimit) {
		t.Fatal("third search accepted")
	}
	s.searchID = result.SearchID
	s.searchExpiry = time.Now().Add(-time.Second)
	if _, err = s.Route(call(s, `{"product_id":"milk","search_id":"`+result.SearchID+`"}`), cat); !errors.Is(err, ErrStale) {
		t.Fatal("expired selection accepted")
	}
}
func TestPrivateBoundary(t *testing.T) {
	registry := NewRegistry()
	s := NewSession(context.Background(), "session", "en-US", nil)
	registry.add(s)
	defer registry.remove(s.ID)
	s.BeginTurn()
	classify(t, s)
	handler := PrivateHandler(registry, &fixtureCatalog{})
	body, _ := json.Marshal(call(s, `{"query":"milk"}`))
	for _, tc := range []struct {
		path, auth string
		want       int
	}{{"/internal/tools/search_catalog", "", 401}, {"/internal/tools/delete_all", "Bearer " + s.capability, 404}, {"/internal/tools/search_catalog", "Bearer " + s.capability, 200}} {
		req := httptest.NewRequest("POST", tc.path, strings.NewReader(string(body)))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", tc.auth)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
		if w.Code != tc.want {
			t.Fatalf("%s: %d", tc.path, w.Code)
		}
	}
	cap := s.capability
	s.Close()
	if s.Authenticate(cap) {
		t.Fatal("revoked capability accepted")
	}
}
func TestOutputBacklogAndSilence(t *testing.T) {
	q := newOutbox()
	for i := 0; i < 3; i++ {
		if err := q.push(frame{kind: 2, data: make([]byte, 16000)}); err != nil {
			t.Fatal(err)
		}
	}
	if q.push(frame{kind: 2, data: []byte{0, 0}}) == nil {
		t.Fatal("backlog unbounded")
	}
	q.flush()
	if q.bytes != 0 {
		t.Fatal("flush leaked bytes")
	}
	if voiced(make([]byte, 3200)) {
		t.Fatal("silence counted as activity")
	}
	if !voiced([]byte{0xff, 0x7f, 0xff, 0x7f}) {
		t.Fatal("speech energy not detected")
	}
}
func TestConcurrentTurnAndClose(t *testing.T) {
	s := NewSession(context.Background(), "session", "en-US", nil)
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); s.BeginTurn(); _ = s.Authenticate("invalid"); _ = s.Turn() }()
	}
	s.Close()
	wg.Wait()
}

func TestFailedTurnSealsPendingToolsAndAllowsFreshSpeech(t *testing.T) {
	emitted := 0
	s := NewSession(context.Background(), "session", "en-US", func(Event) error { emitted++; return nil })
	defer s.Close()
	turn := s.BeginTurn()
	classify(t, s)
	blocked := make(chan struct{})
	done := make(chan error)
	invocation := call(s, `{"query":"milk"}`)
	go func() { _, err := s.Search(invocation, &fixtureCatalog{delay: blocked}); done <- err }()
	if !s.FailTurn(turn) || s.FailTurn(turn) {
		t.Fatal("failed turn was not sealed exactly once")
	}
	close(blocked)
	if err := <-done; err == nil || emitted != 0 {
		t.Fatal("failed turn published pending search", err)
	}
	if s.AudioAllowed(turn) || s.RegisterClassification(turn, "classification-attempt-late", "conversation") == nil {
		t.Fatal("failed turn unlocked output")
	}
	next := s.BeginTurn()
	if s.FailTurn(turn) {
		t.Fatal("late failure cancelled a fresh turn")
	}
	if err := s.RegisterClassification(next, "classification-attempt-fresh", "conversation"); err != nil || !s.AudioAllowed(next) {
		t.Fatal("healthy connection could not continue", err)
	}
}

func TestSpeechEnergyMatchesBrowserRMSBoundary(t *testing.T) {
	for _, tc := range []struct {
		level  int16
		stride int
		want   bool
	}{{400, 1, false}, {499, 1, false}, {500, 1, true}, {2000, 8, true}} {
		pcm := make([]byte, 3200)
		for i := 0; i < 1600; i += tc.stride {
			binary.LittleEndian.PutUint16(pcm[2*i:], uint16(tc.level))
		}
		if got := voiced(pcm); got != tc.want {
			t.Fatalf("level %d stride %d: got %v", tc.level, tc.stride, got)
		}
	}
}
