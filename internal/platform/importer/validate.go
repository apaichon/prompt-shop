package importer

import (
	"math"
	"regexp"
	"strings"
	"unicode/utf8"
)

var idPattern = regexp.MustCompile(`^[a-z0-9-]{1,64}$`)
var languages = map[string]bool{"en-US": true, "th-TH": true, "zh-CN": true, "ja-JP": true}

type state struct {
	Store    *Store
	Aisles   map[string]Aisle
	Nodes    map[string]Node
	Edges    map[string]Edge
	Shelves  map[string]Shelf
	Products map[string]Product
}

func emptyState() state {
	return state{nil, map[string]Aisle{}, map[string]Node{}, map[string]Edge{}, map[string]Shelf{}, map[string]Product{}}
}
func edgeKey(e Edge) string {
	if e.From > e.To {
		return e.To + "/" + e.From
	}
	return e.From + "/" + e.To
}
func merge(old state, b Batch) state {
	out := emptyState()
	out.Store = old.Store
	if b.Store != nil {
		out.Store = b.Store
	}
	for k, v := range old.Aisles {
		out.Aisles[k] = v
	}
	for _, v := range b.Aisles {
		out.Aisles[v.ID] = v
	}
	for k, v := range old.Nodes {
		out.Nodes[k] = v
	}
	for _, v := range b.Nodes {
		out.Nodes[v.ID] = v
	}
	for k, v := range old.Edges {
		out.Edges[k] = v
	}
	for _, v := range b.Edges {
		out.Edges[edgeKey(v)] = v
	}
	for k, v := range old.Shelves {
		out.Shelves[k] = v
	}
	for _, v := range b.Shelves {
		out.Shelves[v.ID] = v
	}
	for k, v := range old.Products {
		out.Products[k] = v
	}
	for _, v := range b.Products {
		out.Products[v.ID] = v
	}
	return out
}
func validate(b Batch, s state) error {
	errors := []RowError{}
	add := func(c string, i int, f, code, msg string) { errors = append(errors, RowError{c, i, f, code, msg}) }
	textOK := func(v string, n int) bool {
		return strings.TrimSpace(v) != "" && utf8.RuneCountInString(v) <= n && !strings.ContainsRune(v, 0)
	}
	if b.SchemaVersion != 1 {
		add("batch", 0, "schema_version", "INVALID_VERSION", "schema_version must be 1")
	}
	if b.StoreID != StoreID {
		add("batch", 0, "store_id", "INVALID_STORE", "store_id must be demo-store")
	}
	if !idPattern.MatchString(b.ImportVersion) {
		add("batch", 0, "import_version", "INVALID_ID", "invalid import version")
	}
	if b.Products == nil || len(b.Products) > 10000 {
		add("products", 0, "", "INVALID_COUNT", "products array is required, maximum 10000")
	}
	if s.Store == nil {
		add("store", 0, "", "REQUIRED", "initial import requires store")
		return &ValidationError{errors}
	}
	store := s.Store
	finite := func(v float64) bool { return !math.IsNaN(v) && !math.IsInf(v, 0) }
	coord := func(x, y float64) bool {
		return finite(x) && finite(y) && x >= 0 && y >= 0 && x <= store.Width && y <= store.Height
	}
	if !textOK(store.Name, 120) || !finite(store.Width) || !finite(store.Height) || store.Width <= 0 || store.Height <= 0 || store.Entrance != "entrance" {
		add("store", 0, "", "INVALID_STORE", "name, positive dimensions and entrance node are required")
	}
	seen := map[string]map[string]bool{}
	id := func(c string, i int, v string) {
		if seen[c] == nil {
			seen[c] = map[string]bool{}
		}
		if !idPattern.MatchString(v) {
			add(c, i, "id", "INVALID_ID", "use 1-64 lowercase letters, digits or hyphens")
		}
		if seen[c][v] {
			add(c, i, "id", "DUPLICATE_ID", "duplicate ID in batch")
		}
		seen[c][v] = true
	}
	for i, v := range b.Aisles {
		id("aisles", i, v.ID)
	}
	for i, v := range b.Nodes {
		id("nodes", i, v.ID)
	}
	for i, v := range b.Shelves {
		id("shelves", i, v.ID)
	}
	for i, v := range b.Products {
		id("products", i, v.ID)
	}
	edgeSeen := map[string]bool{}
	for i, e := range b.Edges {
		key := edgeKey(e)
		if edgeSeen[key] {
			add("edges", i, "", "DUPLICATE_EDGE", "duplicate or reversed edge")
		}
		edgeSeen[key] = true
	}
	// Report input indices when present, -1 for an existing record invalidated by a map edit.
	index := func(c, key string) int {
		switch c {
		case "aisles":
			for i, v := range b.Aisles {
				if v.ID == key {
					return i
				}
			}
		case "nodes":
			for i, v := range b.Nodes {
				if v.ID == key {
					return i
				}
			}
		case "shelves":
			for i, v := range b.Shelves {
				if v.ID == key {
					return i
				}
			}
		case "products":
			for i, v := range b.Products {
				if v.ID == key {
					return i
				}
			}
		case "edges":
			for i, v := range b.Edges {
				if edgeKey(v) == key {
					return i
				}
			}
		}
		return -1
	}
	for key, a := range s.Aisles {
		i := index("aisles", key)
		if !textOK(a.Label, 80) {
			add("aisles", i, "label", "INVALID_TEXT", "label must be 1-80 characters")
		}
		valid := len(a.Polygon) >= 3 && len(a.Polygon) <= 64
		for _, p := range a.Polygon {
			valid = valid && coord(p.X, p.Y)
		}
		if valid {
			valid = simplePolygon(a.Polygon)
		}
		if !valid {
			add("aisles", i, "polygon", "INVALID_POLYGON", "polygon must be simple, nonzero-area and within map bounds")
		}
	}
	for key, n := range s.Nodes {
		i := index("nodes", key)
		if !coord(n.X, n.Y) {
			add("nodes", i, "", "INVALID_COORDINATES", "node is outside map")
		}
		if !textOK(n.Label, 80) {
			add("nodes", i, "label", "INVALID_TEXT", "label must be 1-80 characters")
		}
		for _, a := range s.Aisles {
			if inside(Point{n.X, n.Y}, a.Polygon) {
				add("nodes", i, "", "BLOCKED_NODE", "node lies inside fixture")
				break
			}
		}
	}
	if _, ok := s.Nodes[store.Entrance]; !ok {
		add("store", 0, "entrance_node_id", "INVALID_REFERENCE", "entrance node does not exist")
	}
	adjacent := map[string][]string{}
	for key, e := range s.Edges {
		i := index("edges", key)
		a, ao := s.Nodes[e.From]
		z, zo := s.Nodes[e.To]
		if !ao || !zo || e.From == e.To {
			add("edges", i, "", "INVALID_REFERENCE", "edge requires two different existing nodes")
			continue
		}
		if !finite(e.Weight) || e.Weight <= 0 {
			add("edges", i, "weight", "INVALID_WEIGHT", "weight must be positive and finite")
		}
		blocked := false
		for _, aisle := range s.Aisles {
			if crossesInterior(Point{a.X, a.Y}, Point{z.X, z.Y}, aisle.Polygon) {
				blocked = true
				break
			}
		}
		if blocked {
			add("edges", i, "", "BLOCKED_EDGE", "edge crosses fixture interior")
			continue
		}
		adjacent[e.From] = append(adjacent[e.From], e.To)
		adjacent[e.To] = append(adjacent[e.To], e.From)
	}
	reached := map[string]bool{store.Entrance: true}
	q := []string{store.Entrance}
	for len(q) > 0 {
		n := q[0]
		q = q[1:]
		for _, v := range adjacent[n] {
			if !reached[v] {
				reached[v] = true
				q = append(q, v)
			}
		}
	}
	for key, shelf := range s.Shelves {
		i := index("shelves", key)
		if _, ok := s.Aisles[shelf.AisleID]; !ok {
			add("shelves", i, "aisle_id", "INVALID_REFERENCE", "aisle does not exist")
		}
		if !textOK(shelf.Label, 80) {
			add("shelves", i, "label", "INVALID_TEXT", "label must be 1-80 characters")
		}
		if !coord(shelf.X, shelf.Y) {
			add("shelves", i, "", "INVALID_COORDINATES", "shelf is outside map")
		}
		if shelf.NodeID != nil {
			if _, ok := s.Nodes[*shelf.NodeID]; !ok {
				add("shelves", i, "map_node_id", "INVALID_REFERENCE", "node does not exist")
			} else if !reached[*shelf.NodeID] {
				add("shelves", i, "map_node_id", "UNREACHABLE", "mapped shelf must be reachable from entrance")
			}
		}
	}
	// Only imported products need scalar checks; all merged products need FK checks.
	for key, product := range s.Products {
		if _, ok := s.Shelves[product.ShelfID]; !ok {
			add("products", index("products", key), "shelf_id", "INVALID_REFERENCE", "shelf does not exist")
		}
	}
	for i, product := range b.Products {
		if !textOK(product.Name, 120) {
			add("products", i, "name", "INVALID_TEXT", "name must be 1-120 characters")
		}
		if !textOK(product.Category, 80) {
			add("products", i, "category", "INVALID_TEXT", "category must be 1-80 characters")
		}
		if product.State != "draft" && product.State != "published" && product.State != "archived" {
			add("products", i, "state", "INVALID_STATE", "invalid publication state")
		}
		if len(product.Aliases) < 1 || len(product.Aliases) > 20 {
			add("products", i, "aliases", "INVALID_COUNT", "provide 1-20 aliases")
		}
		aliases := map[string]bool{}
		english := false
		for _, a := range product.Aliases {
			if !languages[a.Language] || !textOK(a.Text, 120) || Normalize(a.Text) == "" {
				add("products", i, "aliases", "INVALID_ALIAS", "invalid language or alias text")
			}
			key := a.Language + "/" + Normalize(a.Text)
			if aliases[key] {
				add("products", i, "aliases", "DUPLICATE_ALIAS", "duplicate normalized alias")
			}
			aliases[key] = true
			english = english || a.Language == "en-US"
		}
		if product.State == "published" && !english {
			add("products", i, "aliases", "ENGLISH_REQUIRED", "published demo product requires English alias")
		}
	}
	if len(errors) > 0 {
		return &ValidationError{errors}
	}
	return nil
}
