package httpserver

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/jackc/pgx/v5/pgxpool"
)

func TestHealthAndSafeErrors(t *testing.T) {
	app := New(Dependencies{ReadinessMode: "full", Checks: []Check{func(context.Context) error { return errors.New("postgres://secret") }}, Register: func(r fiber.Router) {
		r.Get("/failure", func(*fiber.Ctx) error { return errors.New("secret SQL credential") })
	}})
	for path, want := range map[string]int{"/healthz": 200, "/readyz": 503, "/api/missing": 404, "/internal/tools/search_catalog": 404, "/failure": 500} {
		r, err := app.Test(httptest.NewRequest("GET", path, nil))
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(r.Body)
		r.Body.Close()
		if r.StatusCode != want || strings.Contains(string(body), "secret") {
			t.Fatalf("%s: %d %s", path, r.StatusCode, body)
		}
		if r.Header.Get("X-Request-ID") == "" || r.Header.Get("Cache-Control") != "no-store" {
			t.Fatal("missing response metadata")
		}
	}
}
func TestReadyAndSidecarDeadline(t *testing.T) {
	app := New(Dependencies{ReadinessMode: "foundation", Checks: []Check{func(context.Context) error { return nil }}})
	r, err := app.Test(httptest.NewRequest("GET", "/readyz", nil))
	if err != nil {
		t.Fatal(err)
	}
	r.Body.Close()
	if r.StatusCode != 200 || r.Header.Get("X-Readiness-Scope") != "foundation" {
		t.Fatal("foundation readiness not labelled")
	}
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { <-r.Context().Done() }))
	defer slow.Close()
	start := time.Now()
	if err := SidecarCheck(slow.URL)(context.Background()); err == nil || time.Since(start) > time.Second {
		t.Fatal("sidecar deadline not bounded")
	}
	redirect := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "http://127.0.0.1:1", http.StatusFound)
	}))
	defer redirect.Close()
	if err := SidecarCheck(redirect.URL)(context.Background()); err == nil {
		t.Fatal("redirect accepted")
	}
}
func TestDatabaseCheckReleasesConnections(t *testing.T) {
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL unset")
	}
	// Separate package tests may run concurrently with schema creation: only test
	// missing-store/closed-pool failure here, not another package's seed timing.
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		t.Fatal(err)
	}
	cfg.MaxConns = 1
	pool, err := pgxpool.NewWithConfig(context.Background(), cfg)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 20; i++ {
		_ = DatabaseCheck(pool)(context.Background())
	}
	if pool.Stat().AcquiredConns() != 0 {
		t.Fatal("readiness leaked pool connection")
	}
	pool.Close()
	start := time.Now()
	if err := DatabaseCheck(pool)(context.Background()); err == nil || time.Since(start) > time.Second {
		t.Fatal("closed pool must fail promptly")
	}
}
