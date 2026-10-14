package catalog

import (
	"strings"
	"unicode"

	"github.com/apaichon/prompt-shop/internal/platform/importer"
)

// Function words in the frozen English prompts. Product words such as
// "whole", "white", and "ground" stay searchable.
var stopwords = map[string]struct{}{
	"a": {}, "an": {}, "the": {}, "where": {}, "is": {}, "are": {}, "can": {},
	"i": {}, "me": {}, "my": {}, "we": {}, "you": {}, "find": {}, "show": {},
	"looking": {}, "need": {}, "want": {}, "get": {}, "have": {}, "for": {},
	"to": {}, "of": {}, "in": {}, "on": {}, "at": {}, "from": {}, "am": {},
	"do": {}, "does": {}, "please": {}, "some": {}, "any": {}, "there": {},
	"what": {}, "which": {}, "who": {}, "how": {},
}

// NormalizeQuery folds case, compatibility characters, and punctuation so
// stored aliases and spoken prompts compare the same way.
func NormalizeQuery(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			b.WriteRune(r)
		} else {
			b.WriteByte(' ')
		}
	}
	return importer.Normalize(b.String())
}

func contentTokens(normalized string) []string {
	fields := strings.Fields(normalized)
	out := make([]string, 0, len(fields))
	for _, field := range fields {
		if _, skip := stopwords[field]; skip {
			continue
		}
		out = append(out, field)
	}
	return out
}
