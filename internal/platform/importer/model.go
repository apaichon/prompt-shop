// Package importer owns the operator-only versioned catalog import boundary.
package importer

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"reflect"
	"strings"
	"unicode/utf8"

	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
)

const MaxBytes = 10 << 20
const StoreID = "demo-store"

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}
type Store struct {
	Name     string  `json:"name"`
	Width    float64 `json:"map_width"`
	Height   float64 `json:"map_height"`
	Entrance string  `json:"entrance_node_id"`
}
type Aisle struct {
	ID      string  `json:"id"`
	Label   string  `json:"label"`
	Polygon []Point `json:"polygon"`
}
type Node struct {
	ID    string  `json:"id"`
	X     float64 `json:"x"`
	Y     float64 `json:"y"`
	Label string  `json:"label"`
}
type Edge struct {
	From   string  `json:"from_node_id"`
	To     string  `json:"to_node_id"`
	Weight float64 `json:"weight"`
}
type Shelf struct {
	ID      string  `json:"id"`
	AisleID string  `json:"aisle_id"`
	Label   string  `json:"label"`
	NodeID  *string `json:"map_node_id"`
	X       float64 `json:"x"`
	Y       float64 `json:"y"`
}
type Alias struct {
	Language string `json:"language"`
	Text     string `json:"text"`
}
type Product struct {
	ID       string  `json:"id"`
	Name     string  `json:"name"`
	Category string  `json:"category"`
	ShelfID  string  `json:"shelf_id"`
	State    string  `json:"state"`
	Aliases  []Alias `json:"aliases"`
}
type Batch struct {
	SchemaVersion int       `json:"schema_version"`
	StoreID       string    `json:"store_id"`
	ImportVersion string    `json:"import_version"`
	Store         *Store    `json:"store,omitempty"`
	Aisles        []Aisle   `json:"aisles,omitempty"`
	Nodes         []Node    `json:"nodes,omitempty"`
	Edges         []Edge    `json:"edges,omitempty"`
	Shelves       []Shelf   `json:"shelves,omitempty"`
	Products      []Product `json:"products"`
}
type RowError struct {
	Collection string `json:"collection"`
	Index      int    `json:"index"`
	Field      string `json:"field"`
	Code       string `json:"code"`
	Message    string `json:"message"`
}
type ValidationError struct {
	Errors []RowError `json:"errors"`
}

func (e *ValidationError) Error() string {
	return fmt.Sprintf("import rejected: %d validation errors", len(e.Errors))
}
func invalid(field, code, msg string) error {
	return &ValidationError{[]RowError{{"batch", 0, field, code, msg}}}
}
func Normalize(s string) string {
	return strings.Join(strings.Fields(cases.Fold().String(norm.NFKC.String(s))), " ")
}

// Decode rejects unknown/duplicate fields, excessive input, invalid UTF-8, and
// multiple documents. The raw hash includes whitespace: version files are immutable.
func Decode(r io.Reader) (Batch, []byte, error) {
	var b Batch
	raw, err := io.ReadAll(io.LimitReader(r, MaxBytes+1))
	if err != nil {
		return b, nil, invalid("", "READ_FAILED", "cannot read input")
	}
	if len(raw) > MaxBytes {
		return b, nil, invalid("", "TOO_LARGE", "input exceeds 10 MiB")
	}
	if !utf8.Valid(raw) {
		return b, nil, invalid("", "INVALID_JSON", "input must be UTF-8")
	}
	check := json.NewDecoder(bytes.NewReader(raw))
	if err = uniqueJSON(check); err != nil {
		return b, nil, invalid("", "INVALID_JSON", "invalid or duplicate JSON field")
	}
	if _, err = check.Token(); err != io.EOF {
		return b, nil, invalid("", "INVALID_JSON", "expected one JSON object")
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err = dec.Decode(&b); err != nil {
		return b, nil, invalid("", "INVALID_JSON", "invalid JSON type or unknown field")
	}
	var shape any
	if err = json.Unmarshal(raw, &shape); err != nil {
		return b, nil, invalid("", "INVALID_JSON", "invalid JSON")
	}
	if !requiredFields(shape, reflect.TypeOf(b)) {
		return b, nil, invalid("", "REQUIRED_FIELD", "missing or null required field")
	}
	for i := range b.Edges {
		if b.Edges[i].From > b.Edges[i].To {
			b.Edges[i].From, b.Edges[i].To = b.Edges[i].To, b.Edges[i].From
		}
	}
	return b, raw, nil
}
func uniqueJSON(d *json.Decoder) error {
	t, err := d.Token()
	if err != nil {
		return err
	}
	if delim, ok := t.(json.Delim); ok {
		switch delim {
		case '{':
			seen := map[string]bool{}
			for d.More() {
				k, err := d.Token()
				if err != nil {
					return err
				}
				key, ok := k.(string)
				if !ok || seen[key] {
					return fmt.Errorf("duplicate key")
				}
				seen[key] = true
				if err = uniqueJSON(d); err != nil {
					return err
				}
			}
		case '[':
			for d.More() {
				if err = uniqueJSON(d); err != nil {
					return err
				}
			}
		default:
			return fmt.Errorf("unexpected delimiter")
		}
		_, err = d.Token()
		return err
	}
	return nil
}

func requiredFields(v any, t reflect.Type) bool {
	if t.Kind() == reflect.Pointer {
		if v == nil {
			return t.Elem().Kind() == reflect.String
		}
		return requiredFields(v, t.Elem())
	}
	if v == nil {
		return false
	}
	switch t.Kind() {
	case reflect.Struct:
		m, ok := v.(map[string]any)
		if !ok {
			return false
		}
		known := map[string]bool{}
		for i := 0; i < t.NumField(); i++ {
			f := t.Field(i)
			parts := strings.Split(f.Tag.Get("json"), ",")
			known[parts[0]] = true
			value, present := m[parts[0]]
			optional := len(parts) > 1 && parts[1] == "omitempty"
			if !present {
				if optional {
					continue
				}
				return false
			}
			if !requiredFields(value, f.Type) {
				return false
			}
		}
		for key := range m {
			if !known[key] {
				return false
			}
		}
	case reflect.Slice:
		a, ok := v.([]any)
		if !ok {
			return false
		}
		for _, item := range a {
			if !requiredFields(item, t.Elem()) {
				return false
			}
		}
	}
	return true
}
