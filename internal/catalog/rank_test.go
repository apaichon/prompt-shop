package catalog

import (
	"encoding/json"
	"os"
	"testing"
)

func TestRankingRejectsUnsupportedSuffixes(t *testing.T) {
	items := []Indexed{{Product: Product{ID: "milk-whole", Name: "Whole milk 1 L"}, Aliases: []string{"milk", "whole milk"}}}
	for _, query := range []string{"milk moon cheese", "whole milk dragon eggs", "dragon eggs"} {
		got, ambiguous := Rank(query, items)
		if len(got) != 0 || ambiguous {
			t.Fatalf("unsupported query %q returned %v", query, got)
		}
	}
	got, _ := Rank("whole milk", items)
	if len(got) != 1 || got[0].ID != "milk-whole" {
		t.Fatal("stored whole-milk alias must still match")
	}
}

func TestRankingOrderCapAndAmbiguity(t *testing.T) {
	items := []Indexed{
		{Product: Product{ID: "d", Name: "Milk drink"}},
		{Product: Product{ID: "c", Name: "Milk drink"}},
		{Product: Product{ID: "b", Name: "Milk drink"}},
		{Product: Product{ID: "a", Name: "Milk"}},
	}
	got, ambiguous := Rank("milk", items)
	if len(got) != 3 || !ambiguous || got[0].ID != "a" || got[1].ID != "b" || got[2].ID != "c" {
		t.Fatalf("wrong ranking/cap/ambiguity: %v %v", got, ambiguous)
	}
}

func seedIndex(t *testing.T) []Indexed {
	t.Helper()
	var items []Indexed
	for _, file := range []string{"../../data/demo-store.json", "../../data/catalog-expansion-v2.json"} {
		raw, e := os.ReadFile(file)
		if e != nil {
			t.Fatal(e)
		}
		var seed struct {
			Products []struct {
				ID, Name, Category, State string
				Aliases                   []struct{ Text string }
			}
		}
		if e = json.Unmarshal(raw, &seed); e != nil {
			t.Fatal(e)
		}
		for _, p := range seed.Products {
			if p.State != "published" {
				continue
			}
			item := Indexed{Product: Product{ID: p.ID, Name: p.Name, Category: p.Category}}
			for _, a := range p.Aliases {
				item.Aliases = append(item.Aliases, a.Text)
			}
			items = append(items, item)
		}
	}
	return items
}
func TestSeededGalleryNamesRemainSearchable(t *testing.T) {
	items := seedIndex(t)
	if len(items) != 120 {
		t.Fatalf("expected120published seed products; got%d", len(items))
	}
	for _, item := range items {
		t.Run(item.Product.ID, func(t *testing.T) {
			got, _ := Rank(item.Product.Name, items)
			for _, p := range got {
				if p.ID == item.Product.ID {
					return
				}
			}
			t.Fatal("gallery product not returned by its own name")
		})
	}
}
func TestSpokenBakeryWordForms(t *testing.T) {
	items := seedIndex(t)
	for query, id := range map[string]string{"bagel": "bagels", "blueberry muffin": "blueberry-muffins", "burger bun": "burger-buns", "cinnamon roll": "cinnamon-rolls", "croissant": "croissants", "tortilla": "tortillas", "baguettes": "baguette", "chocolate cakes": "chocolate-cake", "toothbrush": "toothbrushes"} {
		t.Run(query, func(t *testing.T) {
			got, ambiguous := Rank("Where can I find a "+query+"?", items)
			if len(got) != 1 || got[0].ID != id || ambiguous {
				t.Fatalf("missing/wrong word-form match: %v", got)
			}
		})
	}
	for _, query := range []string{"moon rock bagel", "gluten free muffin", "sugar free cinnamon roll", "burger bunny", "cinnamon roller", "blueberry moon muffins", "bakery moon cheese", "couscou", "hummu", "asparagu"} {
		got, _ := Rank(query, items)
		if len(got) != 0 {
			t.Fatalf("unsupported modifier/stem accepted: %q", query)
		}
	}
	got, ambiguous := Rank("muffin", items)
	if len(got) != 2 || !ambiguous {
		t.Fatal("muffin must clarify blueberry versus English")
	}
	got, ambiguous = Rank("Where is the bakery?", items)
	if len(got) != 3 || !ambiguous {
		t.Fatal("category should offer bounded candidates")
	}
	for _, p := range got {
		if p.Category != "Bakery" {
			t.Fatal("category crossed")
		}
	}
}
func TestExactWordFormOutranksInflectionAndAliases(t *testing.T) {
	items := []Indexed{{Product: Product{ID: "a-plural", Name: "Bagels"}}, {Product: Product{ID: "z-exact", Name: "Bagel"}}, {Product: Product{ID: "b-alias", Name: "Breakfast ring"}, Aliases: []string{"bagel"}}}
	got, ambiguous := Rank("bagel", items)
	if !ambiguous || len(got) != 3 || got[0].ID != "b-alias" || got[1].ID != "z-exact" || got[2].ID != "a-plural" {
		t.Fatal("exact name/alias priority changed")
	}
}
