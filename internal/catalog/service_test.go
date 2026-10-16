package catalog

import (
	"context"
	"encoding/json"
	"io"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/apaichon/prompt-shop/internal/voice"
	"github.com/gofiber/fiber/v2"
	"github.com/jackc/pgx/v5/pgxpool"
)

func TestShortestUsesStoredWeightsAndRejectsDisconnectedDestination(t *testing.T) {
	m := StoreMap{Origin: "entrance", Nodes: []Node{{ID: "entrance"}, {ID: "junction"}, {ID: "shelf"}, {ID: "isolated"}}, Edges: []Edge{{From: "entrance", To: "shelf", Weight: 10}, {From: "entrance", To: "junction", Weight: 1}, {From: "junction", To: "shelf", Weight: 2}}}
	path, distance := shortest(m, "shelf")
	if strings.Join(path, ",") != "entrance,junction,shelf" || distance != 3 {
		t.Fatal(path, distance)
	}
	if path, _ := shortest(m, "isolated"); path != nil {
		t.Fatal("disconnected route invented", path)
	}
	path, distance = shortest(m, "entrance")
	if len(path) != 1 || distance != 0 {
		t.Fatal(path, distance)
	}
}

// This opt-in test performs only readonly queries on an already seeded local
// database. Unlike schema-reset integration fixtures it never changes user data.
func TestSeededReadonlyCatalogAndHTTP(t *testing.T) {
	url := os.Getenv("CATALOG_READ_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("set CATALOG_READ_TEST_DATABASE_URL to the local seeded readonly principal")
	}
	pool, err := pgxpool.New(context.Background(), url)
	if err != nil {
		t.Fatal("database configuration invalid")
	}
	defer pool.Close()
	s := NewService(pool)
	s.Limiter = nil
	app := fiber.New(fiber.Config{DisableStartupMessage: true})
	s.Register(app)
	request := func(method, path, body string) (int, []byte) {
		t.Helper()
		req := httptest.NewRequest(method, path, strings.NewReader(body))
		if method == "POST" {
			req.Header.Set("Content-Type", "application/json")
		}
		res, e := app.Test(req, 3000)
		if e != nil {
			t.Fatal(e)
		}
		defer res.Body.Close()
		raw, e := io.ReadAll(res.Body)
		if e != nil {
			t.Fatal(e)
		}
		return res.StatusCode, raw
	}
	status, raw := request("GET", "/api/store-map", "")
	var m StoreMap
	if status != 200 || json.Unmarshal(raw, &m) != nil || m.Origin != "entrance" || len(m.Aisles) != 8 || len(m.Nodes) == 0 {
		t.Fatal("real store map unavailable", status)
	}
	result, err := s.Search(context.Background(), "Where is the whole milk?", "en-US")
	if err != nil || len(result.Candidates) == 0 || result.Candidates[0].ID != "milk-whole-1l" {
		t.Fatal("stored product not found", err)
	}
	route, err := s.Route(context.Background(), result.Candidates[0].ID)
	if err != nil || route.Product.Shelf.ID == "" || len(route.Points) != len(route.NodeIDs) || route.NodeIDs[0] != "entrance" {
		t.Fatal("stored walking route unavailable", err)
	}
	for _, id := range []string{"example-draft", "example-archived", "missing-product"} {
		status, _ = request("POST", "/api/routes", `{"product_id":"`+id+`","origin_node_id":"entrance"}`)
		if status != 404 {
			t.Fatalf("inactive/missing product %s returned %d", id, status)
		}
	}
	for _, body := range []string{`{"query":"milk","query":"rice","language":"en-US"}`, `{"query":"milk","language":"en-US","url":"https://example.test"}`, `{"query":"","language":"en-US"}`} {
		status, _ = request("POST", "/api/search", body)
		if status != 400 {
			t.Fatal("invalid search accepted", status)
		}
	}
	status, raw = request("POST", "/api/search", `{"query":"milk","language":"en-US"}`)
	var search struct {
		Candidates []voice.Product `json:"candidates"`
		Ambiguous  bool            `json:"ambiguous"`
	}
	if status != 200 || json.Unmarshal(raw, &search) != nil || len(search.Candidates) != 3 || !search.Ambiguous {
		t.Fatal("ambiguity/three-candidate contract failed", status)
	}
	status, _ = request("POST", "/api/routes", `{"product_id":"milk-whole-1l","origin_node_id":"unknown-origin"}`)
	if status != 400 {
		t.Fatal("caller supplied origin accepted")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err = s.Search(ctx, "milk", "en-US"); err == nil {
		t.Fatal("cancelled database request continued")
	}
}
