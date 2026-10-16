package shopauth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/gofiber/fiber/v2"
	"golang.org/x/crypto/bcrypt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

var hashOnce sync.Once
var fixtureHash string

func accounts(t *testing.T) []Account {
	t.Helper()
	hashOnce.Do(func() {
		h, e := bcrypt.GenerateFromPassword([]byte("test-password-only"), 12)
		if e != nil {
			t.Fatal(e)
		}
		fixtureHash = string(h)
	})
	result := make([]Account, 10)
	for i := range result {
		role := "shopper"
		if i == 0 {
			role = "admin"
		}
		result[i] = Account{fmt.Sprintf("demo%02d", i+1), fixtureHash, role}
	}
	return result
}
func request(t *testing.T, app *fiber.App, method, path, body, cookie, csrf, origin string) *http.Response {
	t.Helper()
	r := httptest.NewRequest(method, path, strings.NewReader(body))
	r.Header.Set("Origin", origin)
	r.Header.Set("Cookie", cookie)
	r.Header.Set("X-CSRF-Token", csrf)
	r.Header.Set("Content-Type", "application/json")
	res, e := app.Test(r, 15000)
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { res.Body.Close() })
	return res
}
func TestTenAccountsAndSessionLifecycle(t *testing.T) {
	now := time.Now()
	a, e := New(Config{Origin: "https://shop.test", Accounts: accounts(t), Now: func() time.Time { return now }})
	if e != nil {
		t.Fatal(e)
	}
	app := fiber.New()
	a.Register(app)
	app.Get("/api/products", func(c *fiber.Ctx) error { return c.SendStatus(200) })
	app.Get("/ws/voice", func(c *fiber.Ctx) error { return c.SendStatus(200) })
	var valid func() bool
	app.Get("/api/capture", func(c *fiber.Ctx) error { valid = a.Validator(c); return c.SendStatus(200) })
	login := func(name, cookie string) (string, Session) {
		t.Helper()
		r := request(t, app, "POST", "/api/auth/session", `{"username":"`+name+`","password":"test-password-only"}`, cookie, "", "https://shop.test")
		if r.StatusCode != 200 {
			t.Fatalf("login status %d", r.StatusCode)
		}
		c := r.Cookies()[0]
		if !c.Secure || !c.HttpOnly || c.SameSite != http.SameSiteStrictMode || c.Path != "/" || c.Domain != "" || c.MaxAge != 28800 {
			t.Fatal("unsafe cookie")
		}
		var s Session
		if e := json.NewDecoder(r.Body).Decode(&s); e != nil {
			t.Fatal(e)
		}
		return c.Name + "=" + c.Value, s
	}
	for _, path := range []string{"/api/products", "/api/backoffice/products", "/ws/voice"} {
		if request(t, app, "GET", path, "", "", "", "").StatusCode != 401 {
			t.Fatal("anonymous admitted")
		}
	}
	for i := 1; i <= 10; i++ {
		name := fmt.Sprintf("demo%02d", i)
		cookie, s := login(name, "")
		if s.Username != name || s.ExpiresAt.Sub(now) != 8*time.Hour || (i == 1) != (s.Role == "admin") {
			t.Fatal("identity mismatch")
		}
		if request(t, app, "GET", "/api/products", "", cookie, "", "").StatusCode != 200 {
			t.Fatal("authenticated denied")
		}
	}
	now = now.Add(time.Minute)
	cookie, s := login("demo01", "")
	request(t, app, "GET", "/api/capture", "", cookie, "", "")
	if !valid() {
		t.Fatal("validator failed")
	}
	for _, pair := range [][2]string{{"", "https://shop.test"}, {s.CSRF, "https://evil.test"}} {
		if request(t, app, "DELETE", "/api/auth/session", "", cookie, pair[0], pair[1]).StatusCode != 403 {
			t.Fatal("logout csrf/origin bypass")
		}
	}
	old := cookie
	cookie, s = login("demo02", old)
	if valid() || request(t, app, "GET", "/api/products", "", old, "", "").StatusCode != 401 {
		t.Fatal("rotation replay")
	}
	request(t, app, "GET", "/api/capture", "", cookie, "", "")
	if request(t, app, "DELETE", "/api/auth/session", "", cookie, s.CSRF, "https://shop.test").StatusCode != 204 || valid() {
		t.Fatal("logout failed")
	}
	cookie, _ = login("demo03", "")
	request(t, app, "GET", "/api/capture", "", cookie, "", "")
	now = now.Add(8 * time.Hour)
	if valid() || request(t, app, "GET", "/api/auth/session", "", cookie, "", "").StatusCode != 401 {
		t.Fatal("expiry failed")
	}
}
func TestFailuresAndBounds(t *testing.T) {
	now := time.Now()
	a, _ := New(Config{Origin: "https://shop.test", Accounts: accounts(t), Now: func() time.Time { return now }})
	app := fiber.New()
	a.Register(app)
	good := `{"username":"demo01","password":"test-password-only"}`
	for _, tc := range []struct {
		body, origin string
		status       int
	}{{good, "https://evil.test", 403}, {`{"username":"unknown","password":"test-password-only"}`, "https://shop.test", 401}, {`{"username":"demo01","password":"bad"}`, "https://shop.test", 401}, {`{"username":"demo01","password":"test-password-only","role":"admin"}`, "https://shop.test", 400}, {good + ` {}`, "https://shop.test", 400}} {
		if request(t, app, "POST", "/api/auth/session", tc.body, "", "", tc.origin).StatusCode != tc.status {
			t.Fatal("unexpected auth response")
		}
	}
	for i := 0; i < 10; i++ {
		request(t, app, "POST", "/api/auth/session", `{}`, "", "", "https://shop.test")
	}
	if request(t, app, "POST", "/api/auth/session", good, "", "", "https://shop.test").StatusCode != 429 {
		t.Fatal("rate not bounded")
	}
	now = now.Add(time.Minute)
	a.cfg.OnLogin = func(context.Context, string, string, Session) error { return errors.New("private DB failure") }
	if request(t, app, "POST", "/api/auth/session", good, "", "", "https://shop.test").StatusCode != 503 || len(a.sessions) != 0 {
		t.Fatal("hook failure admitted login")
	}
	a.cfg.OnLogin = nil
	for i := 0; i < 200; i++ {
		a.sessions[fmt.Sprint(i)] = Session{ExpiresAt: now.Add(time.Hour)}
	}
	if request(t, app, "POST", "/api/auth/session", good, "", "", "https://shop.test").StatusCode != 429 {
		t.Fatal("unbounded sessions")
	}
	for _, origin := range []string{"http://shop.test", "https://shop.test/evil", "https://user@shop.test"} {
		if _, e := New(Config{Origin: origin, Accounts: accounts(t)}); e == nil {
			t.Fatal("bad origin accepted")
		}
	}
	cfg := Config{Origin: "https://shop.test", Accounts: accounts(t)[:9]}
	if _, e := New(cfg); e == nil {
		t.Fatal("wrong count accepted")
	}
	cfg.Accounts = accounts(t)
	cfg.Accounts[1] = cfg.Accounts[0]
	if _, e := New(cfg); e == nil {
		t.Fatal("duplicate accepted")
	}
}

func TestAccountFileValidation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "accounts.json")
	for _, body := range []string{`{}`, `[{"username":"demo01","extra":true}]`, strings.Repeat(" ", 16385), `[] []`} {
		if e := os.WriteFile(path, []byte(body), 0600); e != nil {
			t.Fatal(e)
		}
		if _, e := LoadAccounts(path); e == nil {
			t.Fatal("malformed file accepted")
		}
	}
	data, _ := json.Marshal(accounts(t))
	if e := os.WriteFile(path, data, 0600); e != nil {
		t.Fatal(e)
	}
	a, e := LoadAccounts(path)
	if e != nil || len(a) != 10 {
		t.Fatal("valid file rejected")
	}
}
