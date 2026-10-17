package voice

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"testing"
)

type summaryCatalog struct{ products []Product }

func (f summaryCatalog) Search(ctx context.Context, q, lang string) (SearchResult, error) {
	return SearchResult{CatalogVersion: 2, Candidates: f.products}, nil
}
func (f summaryCatalog) Route(ctx context.Context, id string) (RouteResult, error) {
	for _, p := range f.products {
		if p.ID == id {
			return RouteResult{Product: p, CatalogVersion: 2, MapVersion: 1, OriginNodeID: "entrance", NodeIDs: []string{"entrance"}, Points: []Point{{0, 0}}}, nil
		}
	}
	return RouteResult{}, errors.New("missing")
}
func summaryProduct(id string) Product {
	return Product{ID: id, Name: id, Category: "Dairy", Aisle: Location{"a1", "Aisle 1"}, Shelf: Location{"s1", "Shelf 1"}, RouteAvailable: true}
}
func TestSummaryRetainsVerifiedChoicesAndUnresolvedRequests(t *testing.T) {
	var events []Event
	s := NewSession(context.Background(), "session", "en-US", func(e Event) error { events = append(events, e); return nil })
	defer s.Close()
	lookup := func(query string, products []Product, selectID string) {
		t.Helper()
		s.BeginTurn()
		classify(t, s)
		cat := summaryCatalog{products}
		raw, _ := json.Marshal(map[string]string{"query": query})
		r, err := s.Search(call(s, string(raw)), cat)
		if err != nil {
			t.Fatal(err)
		}
		if selectID != "" {
			if len(products) > 1 {
				s.BeginTurn()
				classify(t, s)
			}
			args, _ := json.Marshal(map[string]string{"product_id": selectID, "search_id": r.SearchID})
			if _, err = s.Route(call(s, string(args)), cat); err != nil {
				t.Fatal(err)
			}
		}
	}
	lookup("milk", []Product{summaryProduct("whole"), summaryProduct("oat")}, "whole")
	lookup("milk", []Product{summaryProduct("whole"), summaryProduct("oat")}, "oat")
	lookup("whole", []Product{summaryProduct("whole")}, "whole")
	lookup("mystery", nil, "")
	lookup(" MILK ", []Product{summaryProduct("whole"), summaryProduct("oat")}, "")
	s.BeginTurn()
	classify(t, s)
	inv := call(s, `{}`)
	result, err := s.Summary(inv)
	if err != nil || len(result.Entries) != 4 || !s.AudioAllowed(s.Turn()) {
		t.Fatal(result, err)
	}
	counts := map[string]int{}
	for _, e := range result.Entries {
		counts[e.Status]++
		if e.Status == "confirmed" && len(e.Products) != 1 {
			t.Fatal(e)
		}
	}
	if counts["confirmed"] != 2 || counts["not_found"] != 1 || counts["needs_choice"] != 1 {
		t.Fatal(counts)
	}
	if events[len(events)-1]["requested"] != true {
		t.Fatal("summary request did not display report")
	}
	if _, err = s.Summary(call(s, `{}`)); !errors.Is(err, ErrLimit) {
		t.Fatal("unbounded summary calls", err)
	}
	s.BeginTurn()
	classify(t, s)
	if _, err = s.Summary(inv); !errors.Is(err, ErrStale) {
		t.Fatal("old summary accepted", err)
	}
	other := NewSession(context.Background(), "other", "en-US", nil)
	defer other.Close()
	other.BeginTurn()
	classify(t, other)
	empty, err := other.Summary(call(other, `{}`))
	if err != nil || len(empty.Entries) != 0 {
		t.Fatal("cross-session facts", empty, err)
	}
	s.Close()
	if len(s.history) != 0 {
		t.Fatal("close retained facts")
	}
}
func TestSummaryBoundsAndFactualBoundary(t *testing.T) {
	s := NewSession(context.Background(), "s", "en-US", nil)
	defer s.Close()
	for i := 0; i < 55; i++ {
		s.rememberSearch(fmt.Sprintf("query %d", i), SearchResult{SearchID: fmt.Sprint(i), CatalogVersion: 1, Candidates: []Product{summaryProduct(fmt.Sprint(i))}})
	}
	if len(s.history) != 50 || !s.summarySnapshot().Truncated {
		t.Fatal("unbounded retention")
	}
	for i := range s.history {
		p := summaryProduct("id")
		p.Name = strings.Repeat("界", 120)
		p.Category = strings.Repeat("界", 80)
		p.Aisle.Label = strings.Repeat("界", 80)
		p.Shelf.Label = strings.Repeat("界", 80)
		s.history[i].Products = []Product{p, p, p}
		s.history[i].Query = strings.Repeat("界", 200)
	}
	result := s.summarySnapshot()
	raw, _ := json.Marshal(result)
	if len(raw) > 48000 || !result.Truncated || len(result.Entries) == 0 {
		t.Fatal("unbounded wire", len(raw))
	}
	s.BeginTurn()
	if _, err := s.Summary(call(s, `{}`)); !errors.Is(err, ErrClassification) {
		t.Fatal("bypassed classification", err)
	}
	classify(t, s)
	for _, args := range []string{`null`, ` null `, `{"products":[]}`, `[]`} {
		if _, err := s.Summary(call(s, args)); err == nil {
			t.Fatal("accepted model facts", args)
		}
	}
	s.FailTurn(s.Turn())
	if _, err := s.Summary(call(s, `{}`)); !errors.Is(err, ErrStale) {
		t.Fatal("failed turn summary", err)
	}
}
