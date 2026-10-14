package voice

import (
	"context"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/jackc/pgx/v5/pgxpool"
)

type memoryTickets struct {
	raw      string
	previous string
	t        Ticket
	mu       sync.Mutex
}

func (m *memoryTickets) Issue(ctx context.Context, hash, previous string, t Ticket) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.raw = hash
	m.previous = previous
	m.t = t
	return nil
}
func (m *memoryTickets) Consume(context.Context, string) (Ticket, error) { return m.t, nil }
func TestCookieOriginAndAdmission(t *testing.T) {
	store := &memoryTickets{}
	g, err := NewGateway(GatewayConfig{Origin: "https://shop.example", BridgeSecret: strings.Repeat("x", 32), Enabled: true}, store, &fixtureCatalog{})
	if err != nil {
		t.Fatal(err)
	}
	app := fiber.New()
	g.Register(app)
	req := httptest.NewRequest("POST", "/api/voice/sessions", strings.NewReader(`{"language":"en-US"}`))
	req.Header.Set("Content-Type", "application/json")
	resp, err := app.Test(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 403 {
		t.Fatal(resp.StatusCode)
	}
	req = httptest.NewRequest("POST", "/api/voice/sessions", strings.NewReader(`{"language":"en-US"}`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", "https://shop.example")
	resp, err = app.Test(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 201 {
		t.Fatal(resp.StatusCode)
	}
	cookies := resp.Cookies()
	if len(cookies) != 1 {
		t.Fatal(cookies)
	}
	cookie := cookies[0]
	if !cookie.HttpOnly || !cookie.Secure || cookie.Path != "/" || cookie.MaxAge != 30 || cookie.SameSite != 3 {
		t.Fatal("unsafe cookie")
	}
	if store.raw == cookie.Value || store.raw != tokenHash(cookie.Value) {
		t.Fatal("raw ticket persisted")
	}
}
func TestPostgresAtomicConsume(t *testing.T) {
	dsn := os.Getenv("VOICE_TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("set VOICE_TEST_DATABASE_URL for disposable PostgreSQL")
	}
	ctx := context.Background()
	admin, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer admin.Close()
	schema := "voice_test_" + tokenHash(randomToken())[:12]
	if _, err = admin.Exec(ctx, "CREATE SCHEMA "+schema); err != nil {
		t.Fatal(err)
	}
	defer admin.Exec(ctx, "DROP SCHEMA "+schema+" CASCADE")
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.RuntimeParams["search_path"] = schema
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	_, err = pool.Exec(ctx, `CREATE TABLE voice_tickets(token_hash text PRIMARY KEY,session_id text UNIQUE NOT NULL,language text NOT NULL,expires_at timestamptz NOT NULL,consumed_at timestamptz)`)
	if err != nil {
		t.Fatal(err)
	}
	store := PostgresTickets{Pool: pool}
	hash := tokenHash(randomToken())
	ticket := Ticket{"session-1", "en-US", time.Now().Add(30 * time.Second)}
	if err = store.Issue(ctx, hash, "", ticket); err != nil {
		t.Fatal(err)
	}
	results := make(chan bool, 20)
	for i := 0; i < 20; i++ {
		go func() { _, e := store.Consume(ctx, hash); results <- e == nil }()
	}
	wins := 0
	for i := 0; i < 20; i++ {
		if <-results {
			wins++
		}
	}
	if wins != 1 {
		t.Fatalf("consume winners=%d", wins)
	}
	next := tokenHash(randomToken())
	ticket.SessionID = "session-2"
	if err = store.Issue(ctx, next, hash, ticket); err != nil {
		t.Fatal(err)
	}
	if _, err = pool.Exec(ctx, `UPDATE voice_tickets SET expires_at=now()-interval '1 second' WHERE token_hash=$1`, next); err != nil {
		t.Fatal(err)
	}
	if _, err = store.Consume(ctx, next); err == nil {
		t.Fatal("expired ticket accepted")
	}
}
