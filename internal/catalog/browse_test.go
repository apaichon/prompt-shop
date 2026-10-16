package catalog

import (
	"encoding/json"
	"os"
	"testing"
)

func TestBrowseFiltersAndPagination(t *testing.T) {
	v := snapshot{Version: 2, Products: []Indexed{}}
	for _, name := range []string{"Zebra", "Apple", "Milk"} {
		p := Product{ID: name, Name: name, Category: "Dairy"}
		p.Shelf.ID = "shelf-one"
		v.Products = append(v.Products, Indexed{Product: p})
	}
	result := browse(v, "Dairy", "shelf-one", 2, 2)
	if result.Total != 3 || len(result.Products) != 1 || result.Products[0].Name != "Zebra" || result.Categories[0].Count != 3 {
		t.Fatal(result)
	}
	if len(browse(v, "Unknown", "", 1, 12).Products) != 0 || len(browse(v, "", "missing", 1, 12).Products) != 0 || len(browse(v, "", "", 10000, 24).Products) != 0 {
		t.Fatal("filter escaped")
	}
	for _, raw := range []string{"0", "-1", "1.5", "10001", "+1", "0001"} {
		if _, err := pageNumber(raw, 1, 10000); err == nil {
			t.Fatal(raw)
		}
	}
}
func TestExpandedSeedHas120UniquePublishedProductsAndValidShelves(t *testing.T) {
	var base struct {
		Products []struct {
			ID    string `json:"id"`
			State string `json:"state"`
		}
		Shelves []struct {
			ID string `json:"id"`
		}
	}
	var extra struct {
		Products []struct {
			ID    string `json:"id"`
			State string `json:"state"`
			Shelf string `json:"shelf_id"`
		}
	}
	raw, e := os.ReadFile("../../data/demo-store.json")
	if e != nil {
		t.Fatal(e)
	}
	if e = json.Unmarshal(raw, &base); e != nil {
		t.Fatal(e)
	}
	raw, e = os.ReadFile("../../data/catalog-expansion-v2.json")
	if e != nil {
		t.Fatal(e)
	}
	if e = json.Unmarshal(raw, &extra); e != nil {
		t.Fatal(e)
	}
	ids := map[string]bool{}
	shelves := map[string]bool{}
	published := 0
	for _, s := range base.Shelves {
		shelves[s.ID] = true
	}
	for _, p := range base.Products {
		ids[p.ID] = true
		if p.State == "published" {
			published++
		}
	}
	if len(extra.Products) != 60 {
		t.Fatal("expected 60 additive rows")
	}
	for _, p := range extra.Products {
		if ids[p.ID] || p.State != "published" || !shelves[p.Shelf] {
			t.Fatal("unsafe additive product", p.ID)
		}
		ids[p.ID] = true
		published++
	}
	if published != 120 {
		t.Fatal(published)
	}
}
