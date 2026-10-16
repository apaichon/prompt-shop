package catalog

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/apaichon/prompt-shop/internal/voice"
	"github.com/gofiber/fiber/v2"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const storeID = "demo-store"

var productID = regexp.MustCompile(`^[a-z0-9-]{1,64}$`)
var catalogPage = regexp.MustCompile(`^[1-9][0-9]{0,4}$`)

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}
type Node struct {
	ID    string  `json:"id"`
	Label string  `json:"label"`
	X     float64 `json:"x"`
	Y     float64 `json:"y"`
}
type Aisle struct {
	ID      string  `json:"id"`
	Label   string  `json:"label"`
	Polygon []Point `json:"polygon"`
}
type Edge struct {
	From   string  `json:"from"`
	To     string  `json:"to"`
	Weight float64 `json:"-"`
}
type StoreMap struct {
	StoreID    string   `json:"store_id"`
	Name       string   `json:"name"`
	MapVersion int64    `json:"map_version"`
	Width      float64  `json:"width"`
	Height     float64  `json:"height"`
	Origin     string   `json:"origin_node_id"`
	Aisles     []Aisle  `json:"aisles"`
	Nodes      []Node   `json:"nodes"`
	Edges      []Edge   `json:"edges"`
	Languages  []string `json:"enabled_languages"`
}
type snapshot struct {
	Map      StoreMap
	Version  int64
	Products []Indexed
}
type Service struct {
	Pool    *pgxpool.Pool
	Limiter *Limiter
}

func NewService(pool *pgxpool.Pool) *Service {
	return &Service{Pool: pool, Limiter: NewLimiter(120, 20)}
}
func (f Failure) Error() string { return f.Code }

// Each operation reads one coherent, published-only snapshot using the readonly
// principal. No import/operator credentials, cached product states or model facts.
func (s *Service) load(parent context.Context) (snapshot, error) {
	ctx, cancel := context.WithTimeout(parent, 750*time.Millisecond)
	defer cancel()
	tx, err := s.Pool.BeginTx(ctx, pgx.TxOptions{IsoLevel: pgx.RepeatableRead, AccessMode: pgx.ReadOnly})
	if err != nil {
		return snapshot{}, err
	}
	defer func() {
		cleanup, done := context.WithTimeout(context.Background(), 250*time.Millisecond)
		defer done()
		_ = tx.Rollback(cleanup)
	}()
	v := snapshot{Map: StoreMap{StoreID: storeID, Aisles: []Aisle{}, Nodes: []Node{}, Edges: []Edge{}, Languages: []string{"en-US"}}, Products: []Indexed{}}
	err = tx.QueryRow(ctx, `SELECT name,catalog_version,map_version,map_width,map_height,entrance_node_id FROM stores WHERE id=$1`, storeID).Scan(&v.Map.Name, &v.Version, &v.Map.MapVersion, &v.Map.Width, &v.Map.Height, &v.Map.Origin)
	if err != nil {
		return v, err
	}
	rows, err := tx.Query(ctx, `SELECT id,label,polygon FROM aisles WHERE store_id=$1 ORDER BY id`, storeID)
	if err != nil {
		return v, err
	}
	for rows.Next() {
		var a Aisle
		var raw []byte
		if err = rows.Scan(&a.ID, &a.Label, &raw); err == nil {
			err = json.Unmarshal(raw, &a.Polygon)
		}
		if err != nil {
			rows.Close()
			return v, err
		}
		v.Map.Aisles = append(v.Map.Aisles, a)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return v, err
	}
	rows, err = tx.Query(ctx, `SELECT id,label,x,y FROM map_nodes WHERE store_id=$1 ORDER BY id`, storeID)
	if err != nil {
		return v, err
	}
	for rows.Next() {
		var n Node
		if err = rows.Scan(&n.ID, &n.Label, &n.X, &n.Y); err != nil {
			rows.Close()
			return v, err
		}
		v.Map.Nodes = append(v.Map.Nodes, n)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return v, err
	}
	rows, err = tx.Query(ctx, `SELECT from_node_id,to_node_id,weight FROM map_edges WHERE store_id=$1 ORDER BY from_node_id,to_node_id`, storeID)
	if err != nil {
		return v, err
	}
	var from, to []string
	for rows.Next() {
		var e Edge
		if err = rows.Scan(&e.From, &e.To, &e.Weight); err != nil {
			rows.Close()
			return v, err
		}
		v.Map.Edges = append(v.Map.Edges, e)
		from = append(from, e.From)
		to = append(to, e.To)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return v, err
	}
	reachable := Reachable(v.Map.Origin, from, to)
	rows, err = tx.Query(ctx, `SELECT p.id,p.name,p.category,a.id,a.label,s.id,s.label,COALESCE(s.map_node_id,''),COALESCE(array_agg(pa.alias ORDER BY pa.normalized_alias) FILTER (WHERE pa.alias IS NOT NULL),'{}'::text[]) FROM products p JOIN shelves s ON (s.store_id,s.id)=(p.store_id,p.shelf_id) JOIN aisles a ON (a.store_id,a.id)=(s.store_id,s.aisle_id) LEFT JOIN product_aliases pa ON (pa.store_id,pa.product_id)=(p.store_id,p.id) AND pa.language='en-US' WHERE p.store_id=$1 AND p.state='published' GROUP BY p.id,p.name,p.category,a.id,a.label,s.id,s.label,s.map_node_id ORDER BY p.id`, storeID)
	if err != nil {
		return v, err
	}
	for rows.Next() {
		var item Indexed
		p := &item.Product
		if err = rows.Scan(&p.ID, &p.Name, &p.Category, &p.Aisle.ID, &p.Aisle.Label, &p.Shelf.ID, &p.Shelf.Label, &item.NodeID, &item.Aliases); err != nil {
			rows.Close()
			return v, err
		}
		p.RouteAvailable = reachable[item.NodeID]
		v.Products = append(v.Products, item)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return v, err
	}
	return v, tx.Commit(ctx)
}

func toVoice(p Product) voice.Product {
	return voice.Product{ID: p.ID, Name: p.Name, Category: p.Category, Aisle: voice.Location{ID: p.Aisle.ID, Label: p.Aisle.Label}, Shelf: voice.Location{ID: p.Shelf.ID, Label: p.Shelf.Label}, RouteAvailable: p.RouteAvailable}
}
func (s *Service) Search(ctx context.Context, query, language string) (voice.SearchResult, error) {
	if language != "en-US" {
		return voice.SearchResult{}, Failure{Status: 400, Code: "LANGUAGE_DISABLED", Message: "English is available.", Retryable: false}
	}
	if !utf8.ValidString(query) || strings.TrimSpace(query) == "" || utf8.RuneCountInString(query) > 200 {
		return voice.SearchResult{}, invalidRequest("Enter one item name, up to 200 characters.")
	}
	v, err := s.load(ctx)
	if err != nil {
		return voice.SearchResult{}, err
	}
	items, ambiguous := Rank(query, v.Products)
	result := voice.SearchResult{CatalogVersion: v.Version, Candidates: []voice.Product{}, Ambiguous: ambiguous}
	for _, p := range items {
		result.Candidates = append(result.Candidates, toVoice(p))
	}
	return result, nil
}

// Dijkstra traverses only stored graph edges; ties follow stable node IDs.
func shortest(m StoreMap, destination string) ([]string, float64) {
	distance := map[string]float64{}
	previous := map[string]string{}
	done := map[string]bool{}
	for _, n := range m.Nodes {
		distance[n.ID] = math.Inf(1)
	}
	distance[m.Origin] = 0
	for range m.Nodes {
		current := ""
		best := math.Inf(1)
		for _, n := range m.Nodes {
			d := distance[n.ID]
			if !done[n.ID] && (d < best || (d == best && current != "" && n.ID < current)) {
				current = n.ID
				best = d
			}
		}
		if current == "" || math.IsInf(best, 1) {
			break
		}
		done[current] = true
		if current == destination {
			break
		}
		for _, e := range m.Edges {
			next := ""
			if e.From == current {
				next = e.To
			} else if e.To == current {
				next = e.From
			}
			if next == "" || done[next] {
				continue
			}
			if d := best + e.Weight; d < distance[next] {
				distance[next] = d
				previous[next] = current
			}
		}
	}
	if !done[destination] {
		return nil, 0
	}
	path := []string{destination}
	for path[len(path)-1] != m.Origin {
		prior, ok := previous[path[len(path)-1]]
		if !ok {
			return nil, 0
		}
		path = append(path, prior)
	}
	for i, j := 0, len(path)-1; i < j; i, j = i+1, j-1 {
		path[i], path[j] = path[j], path[i]
	}
	return path, distance[destination]
}
func (s *Service) Route(ctx context.Context, id string) (voice.RouteResult, error) {
	if !productID.MatchString(id) {
		return voice.RouteResult{}, invalidRequest("Invalid product ID.")
	}
	v, err := s.load(ctx)
	if err != nil {
		return voice.RouteResult{}, err
	}
	var selected *Indexed
	for i := range v.Products {
		if v.Products[i].Product.ID == id {
			selected = &v.Products[i]
			break
		}
	}
	if selected == nil {
		return voice.RouteResult{}, Failure{Status: 404, Code: "PRODUCT_NOT_FOUND", Message: "Product not found.", Retryable: false}
	}
	nodes, distance := shortest(v.Map, selected.NodeID)
	if len(nodes) == 0 {
		return voice.RouteResult{}, Failure{Status: 422, Code: "ROUTE_UNAVAILABLE", Message: "The shelf is known, but a walking route is unavailable.", Retryable: false, Product: &selected.Product}
	}
	byID := map[string]Node{}
	for _, n := range v.Map.Nodes {
		byID[n.ID] = n
	}
	result := voice.RouteResult{Product: toVoice(selected.Product), CatalogVersion: v.Version, MapVersion: v.Map.MapVersion, OriginNodeID: v.Map.Origin, NodeIDs: nodes, Points: []voice.Point{}, Steps: []string{}, DistanceUnits: distance}
	result.Steps = append(result.Steps, "Start at the entrance.")
	for i, id := range nodes {
		n := byID[id]
		result.Points = append(result.Points, voice.Point{X: n.X, Y: n.Y})
		if i > 0 {
			result.Steps = append(result.Steps, "Follow the walkway to "+n.Label+".")
		}
	}
	result.Steps = append(result.Steps, fmt.Sprintf("Find %s at %s, %s.", selected.Product.Name, selected.Product.Aisle.Label, selected.Product.Shelf.Label))
	return result, nil
}

type CategoryCount struct {
	Name  string `json:"name"`
	Count int    `json:"count"`
}
type ProductList struct {
	CatalogVersion int64           `json:"catalog_version"`
	Products       []Product       `json:"products"`
	Total          int             `json:"total"`
	Page           int             `json:"page"`
	PageSize       int             `json:"page_size"`
	Categories     []CategoryCount `json:"categories"`
}

func browse(v snapshot, category, shelf string, page, size int) ProductList {
	result := ProductList{CatalogVersion: v.Version, Products: []Product{}, Page: page, PageSize: size, Categories: []CategoryCount{}}
	counts := map[string]int{}
	matches := []Product{}
	for _, item := range v.Products {
		p := item.Product
		counts[p.Category]++
		if (category == "" || category == p.Category) && (shelf == "" || shelf == p.Shelf.ID) {
			matches = append(matches, p)
		}
	}
	sort.Slice(matches, func(i, j int) bool {
		if matches[i].Name == matches[j].Name {
			return matches[i].ID < matches[j].ID
		}
		return matches[i].Name < matches[j].Name
	})
	for name, count := range counts {
		result.Categories = append(result.Categories, CategoryCount{name, count})
	}
	sort.Slice(result.Categories, func(i, j int) bool { return result.Categories[i].Name < result.Categories[j].Name })
	result.Total = len(matches)
	start := (page - 1) * size
	if start < len(matches) {
		end := start + size
		if end > len(matches) {
			end = len(matches)
		}
		result.Products = matches[start:end]
	}
	return result
}
func pageNumber(raw string, fallback, maximum int) (int, error) {
	if raw == "" {
		return fallback, nil
	}
	if !catalogPage.MatchString(raw) {
		return 0, invalidRequest("Invalid catalog page.")
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n > maximum {
		return 0, invalidRequest("Invalid catalog page.")
	}
	return n, nil
}

func (s *Service) Register(r fiber.Router) {
	fail := func(c *fiber.Ctx, err error) error {
		var f Failure
		if !errors.As(err, &f) {
			f = dependencyFailure()
		}
		return writeFailure(c, f)
	}
	admit := func(c *fiber.Ctx) bool { return s.Limiter.Allow(c.IP()) }
	limited := func(c *fiber.Ctx) error {
		return writeFailure(c, Failure{Status: 429, Code: "RATE_LIMITED", Message: "Please wait before retrying.", Retryable: true})
	}
	r.Get("/api/products", func(c *fiber.Ctx) error {
		if !admit(c) {
			return limited(c)
		}
		page, err := pageNumber(c.Query("page"), 1, 10000)
		if err != nil {
			return fail(c, err)
		}
		size, err := pageNumber(c.Query("page_size"), 12, 24)
		if err != nil {
			return fail(c, err)
		}
		category, shelf := strings.TrimSpace(c.Query("category")), c.Query("shelf_id")
		if !utf8.ValidString(category) || utf8.RuneCountInString(category) > 80 || (shelf != "" && !productID.MatchString(shelf)) {
			return fail(c, invalidRequest("Invalid catalog filter."))
		}
		v, err := s.load(c.UserContext())
		if err != nil {
			return fail(c, err)
		}
		return c.JSON(browse(v, category, shelf, page, size))
	})

	r.Get("/api/store-map", func(c *fiber.Ctx) error {
		if !admit(c) {
			return limited(c)
		}
		v, err := s.load(c.UserContext())
		if err != nil {
			return fail(c, err)
		}
		return c.JSON(v.Map)
	})
	r.Post("/api/search", func(c *fiber.Ctx) error {
		if !admit(c) {
			return limited(c)
		}
		var body struct {
			Query    string `json:"query"`
			Language string `json:"language"`
		}
		if c.Get("Content-Type") != "application/json" || decodeJSON(c.Body(), maxCustomerBody, &body) != nil {
			return fail(c, invalidRequest("Invalid search request."))
		}
		result, err := s.Search(c.UserContext(), body.Query, body.Language)
		if err != nil {
			return fail(c, err)
		}
		return c.JSON(fiber.Map{"query": body.Query, "language": body.Language, "catalog_version": result.CatalogVersion, "candidates": result.Candidates, "ambiguous": result.Ambiguous})
	})
	r.Post("/api/routes", func(c *fiber.Ctx) error {
		if !admit(c) {
			return limited(c)
		}
		var body struct {
			ProductID string `json:"product_id"`
			Origin    string `json:"origin_node_id"`
		}
		if c.Get("Content-Type") != "application/json" || decodeJSON(c.Body(), maxCustomerBody, &body) != nil || body.Origin != "entrance" {
			return fail(c, invalidRequest("Choose a product and the entrance origin."))
		}
		result, err := s.Route(c.UserContext(), body.ProductID)
		if err != nil {
			return fail(c, err)
		}
		return c.JSON(result)
	})
}
