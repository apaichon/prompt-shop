package backoffice

import (
	"context"
	"encoding/json"
	"github.com/apaichon/prompt-shop/internal/platform/httpserver"
	"golang.org/x/crypto/bcrypt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

var once sync.Once
var testHash string

func passwordHash(t *testing.T) string {
	t.Helper()
	once.Do(func() {
		v, err := bcrypt.GenerateFromPassword([]byte("task9-test-password-only"), 12)
		if err != nil {
			t.Fatal(err)
		}
		testHash = string(v)
	})
	return testHash
}

type memoryRepository struct {
	sessions map[string]Session
	writes   int
	fail     bool
}

func (m *memoryRepository) Session(_ context.Context, h string, now time.Time) (Session, error) {
	s, ok := m.sessions[h]
	if !ok || !s.ExpiresAt.After(now) {
		return Session{}, errAuth
	}
	return s, nil
}
func (m *memoryRepository) Rotate(_ context.Context, old, new string, s Session, _ time.Time) error {
	delete(m.sessions, old)
	m.sessions[new] = s
	return nil
}
func (m *memoryRepository) Revoke(_ context.Context, h string) error {
	delete(m.sessions, h)
	return nil
}
func (m *memoryRepository) List(context.Context, Filter) (Page, error) {
	return Page{Items: []Product{}}, nil
}
func (m *memoryRepository) Shelves(context.Context) ([]Shelf, error) { return []Shelf{}, nil }
func (m *memoryRepository) Mutate(_ context.Context, _ string, _ time.Time, _ string, _ Input, _ string) (Product, error) {
	m.writes++
	return Product{}, nil
}
func TestAuthorizationRotationExpiry(t *testing.T) {
	now := time.Date(2026, 10, 14, 0, 0, 0, 0, time.UTC)
	repo := &memoryRepository{sessions: map[string]Session{}}
	api, err := New(repo, Config{Origin: "https://portal.test", PasswordHash: passwordHash(t), Now: func() time.Time { return now }})
	if err != nil {
		t.Fatal(err)
	}
	app := httpserver.New(httpserver.Dependencies{Register: api.Register})
	defer app.Shutdown()
	send := func(method, path, body, cookie, csrf, origin string) *http.Response {
		t.Helper()
		r := httptest.NewRequest(method, path, strings.NewReader(body))
		r.Host = "portal.test"
		r.Header.Set("Content-Type", "application/json")
		r.Header.Set("Origin", origin)
		r.Header.Set("X-CSRF-Token", csrf)
		if cookie != "" {
			r.Header.Set("Cookie", cookie)
		}
		response, e := app.Test(r, 4000)
		if e != nil {
			t.Fatal(e)
		}
		return response
	}
	login := func(cookie string) (string, Session) {
		t.Helper()
		r := send("POST", "/api/backoffice/session", `{"password":"task9-test-password-only"}`, cookie, "", "https://portal.test")
		defer r.Body.Close()
		if r.StatusCode != 200 {
			b, _ := io.ReadAll(r.Body)
			t.Fatalf("login %d %s", r.StatusCode, b)
		}
		cookies := r.Cookies()
		if len(cookies) != 1 {
			t.Fatal("missing cookie")
		}
		c := cookies[0]
		if c.Name != cookieName || !c.Secure || !c.HttpOnly || c.Path != "/" || c.Domain != "" || c.SameSite != http.SameSiteStrictMode || c.MaxAge != 28800 {
			t.Fatalf("unsafe cookie attributes: %s", c.Name)
		}
		var s Session
		if e := json.NewDecoder(r.Body).Decode(&s); e != nil {
			t.Fatal(e)
		}
		if s.ExpiresAt.Sub(now) != 8*time.Hour {
			t.Fatal("wrong expiry")
		}
		return c.Name + "=" + c.Value, s
	}
	methods := []struct{ method, path, body string }{{"GET", "/api/backoffice/session", ""}, {"GET", "/api/backoffice/products", ""}, {"GET", "/api/backoffice/shelves", ""}, {"POST", "/api/backoffice/products", `{}`}, {"PUT", "/api/backoffice/products/example", `{}`}, {"POST", "/api/backoffice/products/example/publish", `{}`}, {"POST", "/api/backoffice/products/example/archive", `{}`}, {"DELETE", "/api/backoffice/session", ""}}
	checkDenied := func(cookie string) {
		for _, tc := range methods {
			r := send(tc.method, tc.path, tc.body, cookie, "", "https://portal.test")
			r.Body.Close()
			if r.StatusCode != 401 {
				t.Fatalf("%s %s expected 401, got %d", tc.method, tc.path, r.StatusCode)
			}
		}
	}
	checkDenied("")
	checkDenied(cookieName + "=" + strings.Repeat("a", 43))
	r := send("POST", "/api/backoffice/session", `{"password":"task9-test-password-only"}`, "", "", "https://attacker.test")
	r.Body.Close()
	if r.StatusCode != 403 {
		t.Fatal("login origin allowed")
	}
	cookie, session := login("")
	for _, tc := range methods {
		if tc.method == "GET" {
			continue
		}
		for _, variant := range []struct{ csrf, origin string }{{"", "https://portal.test"}, {"wrong", "https://portal.test"}, {session.CSRFToken, "https://attacker.test"}} {
			r := send(tc.method, tc.path, tc.body, cookie, variant.csrf, variant.origin)
			r.Body.Close()
			if r.StatusCode != 403 {
				t.Fatalf("missing csrf/origin accepted on %s", tc.path)
			}
		}
	}
	if repo.writes != 0 {
		t.Fatal("unauthorized mutation")
	}
	old := cookie
	cookie, session = login(old)
	checkDenied(old)
	r = send("DELETE", "/api/backoffice/session", "", cookie, session.CSRFToken, "https://portal.test")
	r.Body.Close()
	if r.StatusCode != 204 || r.Cookies()[0].MaxAge != -1 {
		t.Fatal("logout must revoke and clear cookie")
	}
	checkDenied(cookie)
	// A controlled clock demonstrates absolute expiry without activity extending it.
	now = now.Add(time.Minute)
	cookie, _ = login("")
	expires := now.Add(8 * time.Hour)
	for i := 0; i < 3; i++ {
		now = now.Add(time.Hour)
		r = send("GET", "/api/backoffice/session", "", cookie, "", "")
		r.Body.Close()
		if r.StatusCode != 200 {
			t.Fatal("valid session rejected")
		}
	}
	now = expires
	checkDenied(cookie)
}
func TestStrictBodiesAndBoundedInput(t *testing.T) {
	for _, body := range []string{`null`, `{}`, `{"name":"a","name":"b"}`, `{"name":"a","extra":true}`, `{"name":null}`, `{"name":"a"} {}`} {
		var in Input
		err := decode([]byte(body), &in)
		if err == nil {
			_, err = validate(in, "create")
		}
		if err == nil {
			t.Fatalf("accepted malformed input %s", body)
		}
	}
	name, category, shelf, id := "Good name", "Pantry", "a01-s01", "new-item"
	aliases := []Alias{{"en-US", "name"}, {"en-US", " ＮＡＭＥ "}}
	if _, err := validate(Input{ID: &id, Name: &name, Category: &category, ShelfID: &shelf, Aliases: &aliases}, "create"); err == nil {
		t.Fatal("duplicate normalized aliases accepted")
	}
	aliases = []Alias{{"en-US", strings.Repeat("a", 121)}}
	if _, err := validate(Input{ID: &id, Name: &name, Category: &category, ShelfID: &shelf, Aliases: &aliases}, "create"); err == nil {
		t.Fatal("overlong alias")
	}
	aliases = []Alias{{"en-US", "good"}}
	p, err := validate(Input{ID: &id, Name: &name, Category: &category, ShelfID: &shelf, Aliases: &aliases}, "create")
	if err != nil || p.ID != id {
		t.Fatal("valid content rejected")
	}
}
func TestLimitsAndCursorBinding(t *testing.T) {
	now := time.Now()
	l := newLimiter(5, 2)
	for i := 0; i < 2; i++ {
		if ok, _ := l.allow("ip", now); !ok {
			t.Fatal("burst rejected")
		}
	}
	if ok, seconds := l.allow("ip", now); ok || seconds != 12 {
		t.Fatal("rate not enforced")
	}
	if ok, _ := l.allow("ip", now.Add(12*time.Second)); !ok {
		t.Fatal("refill failed")
	}
	if _, err := parseFilter("", "not-a-state", ""); err == nil {
		t.Fatal("invalid state")
	}
	if _, err := parseFilter("", "", "../../file"); err == nil {
		t.Fatal("invalid cursor")
	}
}
