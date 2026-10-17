package voice

import (
	"encoding/json"
	"errors"
	"strings"
)

type SummaryEntry struct {
	Query          string    `json:"query"`
	Status         string    `json:"status"`
	CatalogVersion int64     `json:"catalog_version"`
	Products       []Product `json:"products"`
}
type SummaryResult struct {
	Entries   []SummaryEntry `json:"entries"`
	Truncated bool           `json:"truncated"`
}
type summaryRecord struct {
	SummaryEntry
	searchID string
}

// Caller holds the session lock. Only successful authoritative tool results enter
// this memory; model text and transcripts never create summary products/locations.
func (s *Session) rememberSearch(query string, result SearchResult) {
	key := strings.ToLower(strings.Join(strings.Fields(query), " "))
	for i, r := range s.history {
		if r.Status != "confirmed" && strings.ToLower(strings.Join(strings.Fields(r.Query), " ")) == key {
			s.history = append(s.history[:i], s.history[i+1:]...)
			break
		}
	}
	status := "unconfirmed"
	if len(result.Candidates) == 0 {
		status = "not_found"
	} else if result.Ambiguous {
		status = "needs_choice"
	}
	products := append([]Product{}, result.Candidates...)
	s.history = append(s.history, summaryRecord{SummaryEntry{strings.TrimSpace(query), status, result.CatalogVersion, products}, result.SearchID})
	if len(s.history) > 50 {
		s.history = s.history[len(s.history)-50:]
		s.historyTruncated = true
	}
}
func (s *Session) rememberRoute(searchID string, result RouteResult) {
	for i := range s.history {
		if s.history[i].searchID == searchID {
			s.history[i].Status = "confirmed"
			s.history[i].Products = []Product{result.Product}
			s.history[i].CatalogVersion = result.CatalogVersion
			// Preserve different products chosen from repeated broad queries. Refresh
			// repeated locations for the same product instead of duplicating the item.
			for j := 0; j < len(s.history); j++ {
				if j != i && s.history[j].Status == "confirmed" && s.history[j].Products[0].ID == result.Product.ID {
					s.history = append(s.history[:j], s.history[j+1:]...)
					if j < i {
						i--
					}
					j--
				}
			}
			return
		}
	}
}
func (s *Session) summarySnapshot() SummaryResult {
	result := SummaryResult{Entries: []SummaryEntry{}, Truncated: s.historyTruncated}
	for _, r := range s.history {
		e := r.SummaryEntry
		e.Products = append([]Product{}, e.Products...)
		result.Entries = append(result.Entries, e)
	}
	// Keep the complete event below the existing64KB browser frame limit, even
	// when Unicode labels and ambiguous products reach their contractual maxima.
	for len(result.Entries) > 0 {
		raw, _ := json.Marshal(result)
		if len(raw) <= 48000 {
			break
		}
		result.Entries = result.Entries[1:]
		result.Truncated = true
	}
	return result
}
func (s *Session) emitSummary(requested bool) error {
	if s.emit == nil {
		return nil
	}
	result := s.summarySnapshot()
	return s.emit(Event{"type": "summary", "session_id": s.ID, "turn_id": s.turn, "entries": result.Entries, "truncated": result.Truncated, "requested": requested})
}
func (s *Session) Summary(call Call) (SummaryResult, error) {
	var args map[string]json.RawMessage
	if strictJSON(call.Args, &args) != nil || args == nil || len(args) != 0 {
		return SummaryResult{}, errors.New("INVALID_REQUEST")
	}
	ctx, cancel, err := s.beginCall(call, "get_conversation_summary")
	if err != nil {
		return SummaryResult{}, err
	}
	defer cancel()
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.failed || s.turn != call.TurnID || ctx.Err() != nil {
		return SummaryResult{}, ErrStale
	}
	result := s.summarySnapshot()
	if err := s.emitSummary(true); err != nil {
		return SummaryResult{}, err
	}
	s.audioAllowed = true
	return result, nil
}
