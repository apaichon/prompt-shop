package importer

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/apaichon/prompt-shop/migrations"
	"github.com/jackc/pgx/v5/pgxpool"
)

func seed(t *testing.T) (Batch, []byte) {
	t.Helper()
	raw, err := os.ReadFile("../../../data/demo-store.json")
	if err != nil {
		t.Fatal(err)
	}
	b, _, err := Decode(bytes.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	return b, raw
}
func TestSeedAndNormalization(t *testing.T) {
	b, _ := seed(t)
	if err := validate(b, merge(emptyState(), b)); err != nil {
		t.Fatal(err)
	}
	count := 0
	for _, p := range b.Products {
		if p.State == "published" {
			count++
		}
	}
	if count != 60 || len(b.Aisles) != 8 {
		t.Fatalf("seed %d products, %d aisles", count, len(b.Aisles))
	}
	for input, want := range map[string]string{"  ＭＩＬＫ  ": "milk", "Straße": "strasse", "WHOLE\t MILK": "whole milk"} {
		if got := Normalize(input); got != want {
			t.Errorf("normalize %q = %q, want %q", input, got, want)
		}
	}
}
func TestStrictDecode(t *testing.T) {
	_, raw := seed(t)
	cases := [][]byte{[]byte(`{"schema_version":1,"schema_version":1}`), []byte(`{}`), []byte(`null`), append(append([]byte{}, raw...), []byte(` {}`)...), bytes.Replace(raw, []byte(`"x": 5`), []byte(`"unknown": 5`), 1), bytes.Replace(raw, []byte(`"x": 5`), []byte(`"x": null`), 1), []byte(strings.Repeat(" ", MaxBytes+1))}
	for i, raw := range cases {
		if _, _, err := Decode(bytes.NewReader(raw)); err == nil {
			t.Errorf("case %d unexpectedly accepted", i)
		}
	}
}
func TestGeometry(t *testing.T) {
	square := []Point{{2, 2}, {4, 2}, {4, 4}, {2, 4}}
	cases := []struct {
		a, b    Point
		blocked bool
	}{{Point{0, 3}, Point{6, 3}, true}, {Point{0, 0}, Point{6, 6}, true}, {Point{0, 2}, Point{6, 2}, false}, {Point{0, 0}, Point{2, 2}, false}, {Point{3, 3}, Point{3, 3}, true}}
	for _, c := range cases {
		if got := crossesInterior(c.a, c.b, square); got != c.blocked {
			t.Errorf("%v -> %v blocked=%v", c.a, c.b, got)
		}
	}
	if simplePolygon([]Point{{0, 0}, {2, 2}, {0, 2}, {2, 0}}) {
		t.Fatal("bow-tie accepted")
	}
}
func TestInvalidRows(t *testing.T) {
	mutations := map[string]func(*Batch){
		"shelf":          func(b *Batch) { b.Products[len(b.Products)-1].ShelfID = "absent" },
		"aisle":          func(b *Batch) { b.Shelves[len(b.Shelves)-1].AisleID = "absent" },
		"duplicate":      func(b *Batch) { b.Products = append(b.Products, b.Products[0]) },
		"reverse-edge":   func(b *Batch) { e := b.Edges[0]; e.From, e.To = e.To, e.From; b.Edges = append(b.Edges, e) },
		"edge-weight":    func(b *Batch) { b.Edges[0].Weight = 0 },
		"edge-reference": func(b *Batch) { b.Edges[0].To = "absent" },
		"bounds":         func(b *Batch) { b.Nodes[0].X = -1 },
		"unreachable":    func(b *Batch) { b.Edges = nil },
		"alias":          func(b *Batch) { b.Products[0].Aliases = append(b.Products[0].Aliases, Alias{"en-US", "RED APPLES"}) },
	}
	for name, mutate := range mutations {
		t.Run(name, func(t *testing.T) {
			b, _ := seed(t)
			mutate(&b)
			var ve *ValidationError
			if err := validate(b, merge(emptyState(), b)); !errors.As(err, &ve) || len(ve.Errors) == 0 {
				t.Fatalf("expected row error: %v", err)
			}
		})
	}
}
func disposablePool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL unset; integration requires a disposable database")
	}
	pool, err := pgxpool.New(context.Background(), url)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	// Refuse to reset any database that is not explicitly named as a test database.
	var name string
	if err = pool.QueryRow(context.Background(), `SELECT current_database()`).Scan(&name); err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(name, "_task1") {
		t.Fatal("integration database name must end in _task1")
	}
	if _, err = pool.Exec(context.Background(), `DROP SCHEMA public CASCADE; CREATE SCHEMA public`); err != nil {
		t.Fatal(err)
	}
	if err = migrations.Apply(context.Background(), pool); err != nil {
		t.Fatal(err)
	}
	if err = migrations.Apply(context.Background(), pool); err != nil {
		t.Fatal(err)
	}
	return pool
}
func snapshot(t *testing.T, pool *pgxpool.Pool) string {
	t.Helper()
	out := map[string]json.RawMessage{}
	for _, table := range []string{"stores", "aisles", "map_nodes", "map_edges", "shelves", "products", "product_aliases", "import_batches"} {
		var raw []byte
		query := fmt.Sprintf(`SELECT COALESCE(jsonb_agg(v ORDER BY v::text),'[]'::jsonb) FROM (SELECT to_jsonb(t) v FROM %s t) q`, table)
		if err := pool.QueryRow(context.Background(), query).Scan(&raw); err != nil {
			t.Fatal(err)
		}
		out[table] = raw
	}
	raw, _ := json.Marshal(out)
	return string(raw)
}
func TestIntegrationImport(t *testing.T) {
	pool := disposablePool(t)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	b, raw := seed(t)
	first, err := Import(ctx, pool, bytes.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	if first.CatalogVersion != 1 || first.MapVersion != 1 || first.ProductCount != 62 {
		t.Fatalf("first: %+v", first)
	}
	before := snapshot(t, pool)
	again, err := Import(ctx, pool, bytes.NewReader(raw))
	if err != nil || again.Status != "unchanged" || snapshot(t, pool) != before {
		t.Fatalf("repeat: %+v %v", again, err)
	}
	// Direct FK and graph reachability check, independent of importer validation.
	var products, aisles, reachable int
	if err = pool.QueryRow(ctx, `SELECT count(*) FROM products WHERE state='published'`).Scan(&products); err != nil {
		t.Fatal(err)
	}
	if err = pool.QueryRow(ctx, `SELECT count(*) FROM aisles`).Scan(&aisles); err != nil {
		t.Fatal(err)
	}
	err = pool.QueryRow(ctx, `WITH RECURSIVE walk(id) AS (SELECT entrance_node_id::text FROM stores WHERE id='demo-store' UNION SELECT CASE WHEN e.from_node_id=w.id THEN e.to_node_id::text ELSE e.from_node_id::text END FROM walk w JOIN map_edges e ON e.from_node_id=w.id OR e.to_node_id=w.id WHERE e.store_id='demo-store') SELECT count(*) FROM products p JOIN shelves s ON s.store_id=p.store_id AND s.id=p.shelf_id JOIN walk w ON w.id=s.map_node_id WHERE p.state='published'`).Scan(&reachable)
	if err != nil || products != 60 || aisles != 8 || reachable != 60 {
		t.Fatalf("counts %d/%d/%d: %v", products, aisles, reachable, err)
	}
	t.Logf("seed: %d published, %d aisles, %d reachable products; identical rerun preserved all rows", products, aisles, reachable)
	// Every rejection includes an earlier valid changed row; no partial writes/versions/import ledger.
	for _, kind := range []string{"same-version", "shelf", "aisle", "duplicate", "edge", "merged-map"} {
		t.Run(kind, func(t *testing.T) {
			b, _ := seed(t)
			b.ImportVersion = "invalid-" + kind
			b.Products[0].Name = "Would change"
			switch kind {
			case "same-version":
				b.ImportVersion = "demo-v1"
			case "shelf":
				b.Products[len(b.Products)-1].ShelfID = "missing"
			case "aisle":
				b.Shelves[len(b.Shelves)-1].AisleID = "missing"
			case "duplicate":
				b.Products = append(b.Products, b.Products[0])
			case "edge":
				b.Edges[len(b.Edges)-1].To = "missing"
			case "merged-map":
				b.Store = nil
				b.Aisles = nil
				b.Shelves = nil
				b.Edges = nil
				b.Nodes = []Node{{"a02-n03", 25, 50, "Moved into Aisle 1 fixture"}}
				b.Products = b.Products[:1]
			}
			payload, _ := json.Marshal(b)
			_, err := Import(ctx, pool, bytes.NewReader(payload))
			var ve *ValidationError
			if !errors.As(err, &ve) {
				t.Fatalf("expected row validation error: %v", err)
			}
			if snapshot(t, pool) != before {
				t.Fatal("rejected import changed stored rows")
			}
			t.Logf("%s: %s; snapshot unchanged", kind, ve.Errors[0].Code)
		})
	}
	// Force a database-side failure after valid earlier rows were written; prove
	// rollback covers actual SQL work as well as preflight validation failures.
	if _, err = pool.Exec(ctx, `ALTER TABLE products ADD CONSTRAINT injected_failure CHECK (name <> 'Trigger SQL failure')`); err != nil {
		t.Fatal(err)
	}
	failed, _ := seed(t)
	failed.ImportVersion = "sql-failure"
	failed.Products[0].Name = "Earlier valid update"
	failed.Products[len(failed.Products)-1].Name = "Trigger SQL failure"
	failedRaw, _ := json.Marshal(failed)
	if _, err = Import(ctx, pool, bytes.NewReader(failedRaw)); err == nil {
		t.Fatal("expected injected SQL rejection")
	}
	if snapshot(t, pool) != before {
		t.Fatal("SQL failure did not roll back all rows")
	}
	if _, err = pool.Exec(ctx, `ALTER TABLE products DROP CONSTRAINT injected_failure`); err != nil {
		t.Fatal(err)
	}
	t.Log("database-side constraint failure after earlier writes: full snapshot unchanged")
	// Product-only update replaces aliases; omitted products/map retained.
	b.Store = nil
	b.Aisles = nil
	b.Nodes = nil
	b.Edges = nil
	b.Shelves = nil
	b.ImportVersion = "demo-v2"
	b.Products = b.Products[:1]
	b.Products[0].Name = "Crisp red apples"
	b.Products[0].Aliases = []Alias{{"en-US", "crisp red apples"}}
	raw, _ = json.Marshal(b)
	result, err := Import(ctx, pool, bytes.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	if result.CatalogVersion != 2 || result.MapVersion != 1 {
		t.Fatalf("versions: %+v", result)
	}
	var version int
	var aliases int
	if err = pool.QueryRow(ctx, `SELECT version FROM products WHERE id='red-apples'`).Scan(&version); err != nil {
		t.Fatal(err)
	}
	if err = pool.QueryRow(ctx, `SELECT count(*) FROM product_aliases WHERE product_id='red-apples'`).Scan(&aliases); err != nil {
		t.Fatal(err)
	}
	if version != 2 || aliases != 1 {
		t.Fatalf("update version=%d aliases=%d", version, aliases)
	}
	// Concurrent identical imports serialize to exactly one application.
	b.ImportVersion = "concurrent-v3"
	b.Products[0].Name = "Fresh red apples"
	raw, _ = json.Marshal(b)
	var wg sync.WaitGroup
	results := make(chan Result, 2)
	errs := make(chan error, 2)
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); r, e := Import(ctx, pool, bytes.NewReader(raw)); results <- r; errs <- e }()
	}
	wg.Wait()
	close(results)
	close(errs)
	applied := 0
	for e := range errs {
		if e != nil {
			t.Fatal(e)
		}
	}
	for r := range results {
		if r.Status == "applied" {
			applied++
		}
		if r.CatalogVersion != 3 {
			t.Fatalf("concurrent result %+v", r)
		}
	}
	if applied != 1 {
		t.Fatalf("applied %d times", applied)
	}
	// Same values under a new version do not advance data versions.
	b.ImportVersion = "unchanged-v4"
	raw, _ = json.Marshal(b)
	result, err = Import(ctx, pool, bytes.NewReader(raw))
	if err != nil || result.CatalogVersion != 3 || result.MapVersion != 1 {
		t.Fatalf("unchanged version %+v %v", result, err)
	}
	t.Log("product update: version increments once; aliases replaced; concurrent imports serialize; unchanged payload does not bump data versions")
}
