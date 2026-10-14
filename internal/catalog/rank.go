package catalog

import (
	"strings"

	"github.com/apaichon/prompt-shop/internal/platform/importer"
)

// Rank orders published products by exact name/alias, then bounded prefix,
// then coverage of every content token. Ties break by product ID. At most
// three products are returned. ambiguous is true when more than one product matched.
func Rank(query string, items []Indexed) ([]Product, bool) {
	full := NormalizeQuery(query)
	tokens := contentTokens(full)
	phrase := strings.Join(tokens, " ")
	hits := make([]hit, 0)
	for _, item := range items {
		tier, ok := bestTier(full, phrase, tokens, item)
		if ok {
			hits = append(hits, hit{tier, item})
		}
	}
	for i := 1; i < len(hits); i++ {
		j := i
		for j > 0 && worse(hits[j-1], hits[j]) {
			hits[j-1], hits[j] = hits[j], hits[j-1]
			j--
		}
	}
	ambiguous := len(hits) > 1
	if len(hits) > 3 {
		hits = hits[:3]
	}
	out := make([]Product, 0, len(hits))
	for _, h := range hits {
		out = append(out, h.item.Product)
	}
	return out, ambiguous
}

type hit struct {
	tier int
	item Indexed
}

func worse(a, b hit) bool {
	if a.tier != b.tier {
		return a.tier > b.tier
	}
	return a.item.Product.ID > b.item.Product.ID
}

func bestTier(full, phrase string, tokens []string, item Indexed) (int, bool) {
	names := forms(item)
	prefix := false
	for _, name := range names {
		if name == full || (phrase != "" && name == phrase) {
			return 0, true
		}
		if boundedPrefix(name, full) || (phrase != "" && boundedPrefix(name, phrase)) {
			prefix = true
		}
	}
	if prefix {
		return 1, true
	}
	if len(tokens) == 0 {
		return 0, false
	}
	for _, name := range names {
		set := tokenSet(name)
		all := true
		for _, token := range tokens {
			if _, found := set[token]; !found {
				all = false
				break
			}
		}
		if all {
			return 2, true
		}
	}
	return 0, false
}

func forms(item Indexed) []string {
	out := make([]string, 0, 1+len(item.Aliases))
	if name := importer.Normalize(item.Product.Name); name != "" {
		out = append(out, name)
	}
	for _, alias := range item.Aliases {
		if name := importer.Normalize(alias); name != "" {
			out = append(out, name)
		}
	}
	return out
}

func boundedPrefix(name, query string) bool {
	if name == "" || query == "" || name == query {
		return false
	}
	return strings.HasPrefix(name, query+" ")
}

func tokenSet(normalized string) map[string]struct{} {
	set := make(map[string]struct{})
	for _, field := range strings.Fields(normalized) {
		set[field] = struct{}{}
	}
	return set
}
