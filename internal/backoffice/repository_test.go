package backoffice

import (
	"context"
	"encoding/json"
	"io"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/apaichon/prompt-shop/internal/platform/httpserver"
	"github.com/apaichon/prompt-shop/internal/platform/importer"
	"github.com/apaichon/prompt-shop/migrations"
	"github.com/jackc/pgx/v5/pgxpool"
)

func TestPostgresBackofficeLifecycle(t *testing.T) {
	url := os.Getenv("BACKOFFICE_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("BACKOFFICE_TEST_DATABASE_URL unset; real database gate not executed")
	}
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.ConnConfig.Database != "prompt_shop_task9" {
		t.Fatal("test requires disposable prompt_shop_task9 database")
	}
	ctx := context.Background()
	operator, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer operator.Close()
	if _, err = operator.Exec(ctx, `DROP SCHEMA public CASCADE; CREATE SCHEMA public`); err != nil {
		t.Fatal(err)
	}
	if err = migrations.Apply(ctx, operator); err != nil {
		t.Fatal(err)
	}
	seed, err := os.Open("../../data/demo-store.json")
	if err != nil {
		t.Fatal(err)
	}
	defer seed.Close()
	if _, err = importer.Import(ctx, operator, seed); err != nil {
		t.Fatal(err)
	}
	roles, err := os.ReadFile("../../migrations/roles.sql")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = operator.Exec(ctx, string(roles)); err != nil {
		t.Fatal(err)
	}
	if _, err = operator.Exec(ctx, `DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='prompt_shop_task9_admin') THEN CREATE ROLE prompt_shop_task9_admin LOGIN PASSWORD 'task9-admin-local-only'; END IF; END $$; GRANT prompt_shop_backoffice TO prompt_shop_task9_admin`); err != nil {
		t.Fatal(err)
	}
	adminCfg := cfg.Copy()
	adminCfg.ConnConfig.User = "prompt_shop_task9_admin"
	adminCfg.ConnConfig.Password = "task9-admin-local-only"
	adminCfg.MaxConns = 2
	admin, err := pgxpool.NewWithConfig(ctx, adminCfg)
	if err != nil {
		t.Fatal(err)
	}
	defer admin.Close()
	repo := NewRepository(admin)
	now := time.Now().UTC()
	api, err := New(repo, Config{Origin: "https://portal.test", PasswordHash: passwordHash(t), Now: func() time.Time { return now }})
	if err != nil {
		t.Fatal(err)
	}
	app := httpserver.New(httpserver.Dependencies{Register: api.Register})
	defer app.Shutdown()
	cookie := ""
	csrf := ""
	send := func(method, path, body string, status int) []byte {
		t.Helper()
		r := httptest.NewRequest(method, path, strings.NewReader(body))
		r.Header.Set("Origin", "https://portal.test")
		r.Host = "portal.test"
		r.Header.Set("Content-Type", "application/json")
		r.Header.Set("Cookie", cookie)
		r.Header.Set("X-CSRF-Token", csrf)
		response, e := app.Test(r, 4000)
		if e != nil {
			t.Fatal(e)
		}
		defer response.Body.Close()
		data, _ := io.ReadAll(response.Body)
		if response.StatusCode != status {
			t.Fatalf("%s %s: wanted %d, got %d %s", method, path, status, response.StatusCode, data)
		}
		if method == "POST" && path == "/api/backoffice/session" && status == 200 {
			c := response.Cookies()[0]
			cookie = c.Name + "=" + c.Value
			var session Session
			json.Unmarshal(data, &session)
			csrf = session.CSRFToken
		}
		now = now.Add(5 * time.Second)
		return data
	}
	// Seed a real session for SQL/race coverage. Cost-12 login is separately exercised
	// by the HTTPS Chromium gate; race instrumentation is slower than the 1.5s budget.
	raw := strings.Repeat("a", 43)
	csrf = strings.Repeat("b", 43)
	cookie = cookieName + "=" + raw
	if err = repo.Rotate(ctx, "", tokenHash(raw), Session{ExpiresAt: now.Add(8 * time.Hour), CSRFToken: csrf}, now); err != nil {
		t.Fatal(err)
	}
	var page Page
	json.Unmarshal(send("GET", "/api/backoffice/products", "", 200), &page)
	if len(page.Items) != 50 || page.NextCursor == nil {
		t.Fatal("fixed pagination missing")
	}
	f, err := parseFilter("", "", *page.NextCursor)
	if err != nil {
		t.Fatal(err)
	}
	next, err := repo.List(ctx, f)
	if err != nil || len(next.Items) != 12 {
		t.Fatalf("pagination lost products: %d %v", len(next.Items), err)
	}
	if _, err = parseFilter("milk", "", *page.NextCursor); err == nil {
		t.Fatal("cursor accepted with changed filter")
	}
	var shelves struct{ Items []Shelf }
	json.Unmarshal(send("GET", "/api/backoffice/shelves", "", 200), &shelves)
	if len(shelves.Items) == 0 {
		t.Fatal("no shelf choices")
	}
	content := `{"id":"task9-new-item","name":"QA item","category":"Pantry","shelf_id":"a01-s01","aliases":[{"language":"en-US","text":"qa item"}]}`
	var p Product
	json.Unmarshal(send("POST", "/api/backoffice/products", content, 201), &p)
	if p.State != "draft" || p.Version != 1 {
		t.Fatal("create must be draft v1")
	}
	send("POST", "/api/backoffice/products", content, 409)
	public := func(want bool) {
		t.Helper()
		var visible bool
		if err := operator.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM products p JOIN shelves s ON s.store_id=p.store_id AND s.id=p.shelf_id JOIN aisles a ON a.store_id=s.store_id AND a.id=s.aisle_id WHERE p.store_id='demo-store' AND p.id='task9-new-item' AND p.state='published')`).Scan(&visible); err != nil || visible != want {
			t.Fatal("public read state mismatch")
		}
	}
	public(false)
	json.Unmarshal(send("POST", "/api/backoffice/products/task9-new-item/publish", `{"expected_version":1}`, 200), &p)
	public(true)
	save := `{"name":"QA changed","category":"Pantry","shelf_id":"a02-s03","aliases":[{"language":"en-US","text":"qa changed"}],"expected_version":2}`
	json.Unmarshal(send("PUT", "/api/backoffice/products/task9-new-item", save, 200), &p)
	if p.State != "draft" || p.Version != 3 {
		t.Fatal("editing published must draft")
	}
	public(false)
	send("PUT", "/api/backoffice/products/task9-new-item", save, 409)
	before := send("GET", "/api/backoffice/products?q=qa%20changed", "", 200)
	invalid := `{"name":"Wrong","category":"Pantry","shelf_id":"missing-shelf","aliases":[{"language":"en-US","text":"wrong"}],"expected_version":3}`
	send("PUT", "/api/backoffice/products/task9-new-item", invalid, 422)
	after := send("GET", "/api/backoffice/products?q=qa%20changed", "", 200)
	if string(before) != string(after) {
		t.Fatal("invalid edit altered row/aliases/version")
	}
	send("POST", "/api/backoffice/products/task9-new-item/publish", `{"expected_version":3}`, 200)
	public(true)
	send("POST", "/api/backoffice/products/task9-new-item/archive", `{"expected_version":4}`, 200)
	public(false)
	send("POST", "/api/backoffice/products/task9-new-item/publish", `{"expected_version":5}`, 200)
	public(true)
	var audit int
	operator.QueryRow(ctx, `SELECT count(*) FROM catalog_audit WHERE product_id='task9-new-item'`).Scan(&audit)
	if audit != 6 {
		t.Fatalf("audit expected 6 got %d", audit)
	}
	var rawTokenCount int
	operator.QueryRow(ctx, `SELECT count(*) FROM maintainer_sessions WHERE length(token_hash)<>64`).Scan(&rawTokenCount)
	if rawTokenCount != 0 {
		t.Fatal("raw token stored")
	}
	// Restart repository/app instances over the same database; records and session persist.
	fresh := NewRepository(admin)
	if s, err := fresh.Session(ctx, tokenHash(strings.TrimPrefix(cookie, cookieName+"=")), now); err != nil || s.CSRFToken != csrf {
		t.Fatal("session not durable")
	}
	filtered, err := fresh.List(ctx, Filter{Q: "qa changed"})
	if err != nil || len(filtered.Items) != 1 || filtered.Items[0].ShelfID != "a02-s03" {
		t.Fatal("committed product not durable")
	}
	// Two writers with the same expected version cannot silently overwrite.
	hash := tokenHash(strings.TrimPrefix(cookie, cookieName+"="))
	var input Input
	decode([]byte(`{"expected_version":6}`), &input)
	var wg sync.WaitGroup
	results := make(chan error, 2)
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := fresh.Mutate(ctx, hash, now, "task9-new-item", input, "archive")
			results <- err
		}()
	}
	wg.Wait()
	close(results)
	success, conflicts := 0, 0
	for err := range results {
		if err == nil {
			success++
		} else if err.Error() == "VERSION_CONFLICT" {
			conflicts++
		} else {
			t.Fatal(err)
		}
	}
	if success != 1 || conflicts != 1 {
		t.Fatal("lost update")
	}
	// A blocked store lock must time out and release the admin connection.
	held, err := operator.Begin(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if err = importer.LockStore(ctx, held, storeID); err != nil {
		t.Fatal(err)
	}
	var blocked Input
	decode([]byte(`{"expected_version":7}`), &blocked)
	started := time.Now()
	_, blockedErr := fresh.Mutate(ctx, hash, now, "task9-new-item", blocked, "archive")
	if blockedErr == nil || time.Since(started) > 1500*time.Millisecond {
		t.Fatal("blocked mutation exceeded budget")
	}
	_ = held.Rollback(ctx)
	cleanupDeadline := time.Now().Add(750 * time.Millisecond)
	for admin.Stat().AcquiredConns() != 0 && time.Now().Before(cleanupDeadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if admin.Stat().AcquiredConns() != 0 {
		t.Fatal("timeout leaked database connection beyond cleanup bound")
	}
	// Unmapped/disconnected destination cannot be published, and failures are atomic.
	operator.Exec(ctx, `UPDATE shelves SET map_node_id=NULL WHERE store_id='demo-store' AND id='a02-s03'`)
	send("POST", "/api/backoffice/products/task9-new-item/publish", `{"expected_version":7}`, 422)
	send("DELETE", "/api/backoffice/session", "", 204)
	send("GET", "/api/backoffice/session", "", 401)
	if _, err = fresh.Mutate(ctx, hash, now, "task9-new-item", input, "archive"); err != errAuth {
		t.Fatal("revoked session mutated")
	}
	// Narrow role never grants map editing, DDL or operator import access.
	for _, sql := range []string{`UPDATE shelves SET label='wrong' WHERE id='a01-s01'`, `CREATE TABLE illicit(id int)`, `INSERT INTO import_batches VALUES('demo-store','illicit',repeat('a',64),now(),0)`} {
		if _, err = admin.Exec(ctx, sql); err == nil {
			t.Fatal("backoffice role exceeded privileges")
		}
	}
	admin.Close()
	start := time.Now()
	if _, err = fresh.List(ctx, Filter{}); err == nil || time.Since(start) > time.Second {
		t.Fatal("database outage not bounded")
	}
}
