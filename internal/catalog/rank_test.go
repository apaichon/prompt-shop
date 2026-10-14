package catalog

import "testing"

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
