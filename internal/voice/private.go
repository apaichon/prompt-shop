package voice

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

type Registry struct {
	mu       sync.RWMutex
	sessions map[string]*Session
}

func NewRegistry() *Registry       { return &Registry{sessions: map[string]*Session{}} }
func (r *Registry) add(s *Session) { r.mu.Lock(); defer r.mu.Unlock(); r.sessions[s.ID] = s }
func (r *Registry) remove(id string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if s := r.sessions[id]; s != nil {
		s.Close()
	}
	delete(r.sessions, id)
}
func (r *Registry) get(id string) *Session { r.mu.RLock(); defer r.mu.RUnlock(); return r.sessions[id] }

// PrivateHandler is mounted only by PrivateServer on loopback. Never pass it to
// the public Fiber router. Unknown functions and capabilities fail closed.
func PrivateHandler(registry *Registry, catalog Catalog) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Content-Type", "application/json")
		name := strings.TrimPrefix(r.URL.Path, "/internal/tools/")
		if r.Method != "POST" || r.URL.RawQuery != "" || (name != "search_catalog" && name != "get_product_route" && name != "get_conversation_summary") {
			privateError(w, 404, "INVALID_REQUEST")
			return
		}
		if r.Header.Get("Content-Type") != "application/json" {
			privateError(w, 400, "INVALID_REQUEST")
			return
		}
		raw, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 4096))
		if err != nil {
			privateError(w, 400, "INVALID_REQUEST")
			return
		}
		var call Call
		if strictJSON(raw, &call) != nil {
			privateError(w, 400, "INVALID_REQUEST")
			return
		}
		session := registry.get(call.SessionID)
		auth := r.Header.Get("Authorization")
		if session == nil || !strings.HasPrefix(auth, "Bearer ") || !session.Authenticate(strings.TrimPrefix(auth, "Bearer ")) {
			privateError(w, 401, "FORBIDDEN")
			return
		}
		var result any
		if name == "search_catalog" {
			result, err = session.Search(call, catalog)
		} else if name == "get_conversation_summary" {
			result, err = session.Summary(call)
		} else {
			result, err = session.Route(call, catalog)
		}
		if err != nil {
			code, status := "DEPENDENCY_UNAVAILABLE", 503
			if errors.Is(err, ErrStale) {
				code, status = "STALE_SELECTION", 409
			} else if errors.Is(err, ErrLimit) {
				code, status = "RATE_LIMITED", 429
			} else if errors.Is(err, ErrClassification) {
				code, status = "CLASSIFICATION_REQUIRED", 409
			} else if err.Error() == "INVALID_REQUEST" {
				code, status = "INVALID_REQUEST", 400
			}
			privateError(w, status, code)
			return
		}
		_ = json.NewEncoder(w).Encode(result)
	})
}
func PrivateServer(registry *Registry, catalog Catalog) *http.Server {
	return &http.Server{Addr: "127.0.0.1:8002", Handler: PrivateHandler(registry, catalog), ReadHeaderTimeout: time.Second, ReadTimeout: 2 * time.Second, WriteTimeout: 2 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 4096}
}
func privateError(w http.ResponseWriter, status int, code string) {
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(Event{"error": Event{"code": code, "message": "Voice tool could not complete.", "retryable": status >= 500}})
}
