// Package backoffice owns the protected, single-store catalog maintenance API.
package backoffice

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/apaichon/prompt-shop/internal/platform/importer"
)

const storeID = "demo-store"
const cookieName = "__Host-maintainer"

var idPattern = regexp.MustCompile(`^[a-z0-9-]{1,64}$`)
var tokenPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{43}$`)

type Alias struct {
	Language string `json:"language"`
	Text     string `json:"text"`
}
type Product struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Category  string    `json:"category"`
	ShelfID   string    `json:"shelf_id"`
	Aliases   []Alias   `json:"aliases"`
	State     string    `json:"state"`
	Version   int64     `json:"version"`
	UpdatedAt time.Time `json:"updated_at"`
}
type Label struct {
	ID    string `json:"id"`
	Label string `json:"label"`
}
type Shelf struct {
	ID     string `json:"id"`
	Label  string `json:"label"`
	Aisle  Label  `json:"aisle"`
	Mapped bool   `json:"mapped"`
}
type Session struct {
	ExpiresAt time.Time `json:"expires_at"`
	CSRFToken string    `json:"csrf_token"`
}
type Page struct {
	Items      []Product `json:"items"`
	NextCursor *string   `json:"next_cursor"`
}
type Input struct {
	ID              *string  `json:"id,omitempty"`
	Name            *string  `json:"name,omitempty"`
	Category        *string  `json:"category,omitempty"`
	ShelfID         *string  `json:"shelf_id,omitempty"`
	Aliases         *[]Alias `json:"aliases,omitempty"`
	ExpectedVersion *int64   `json:"expected_version,omitempty"`
}
type Filter struct{ Q, State, Last string }
type fault struct {
	status        int
	code, message string
}

func (f *fault) Error() string { return f.code }
func invalid() error {
	return &fault{422, "VALIDATION_FAILED", "Check the required fields, aliases and shelf."}
}
func conflict() error {
	return &fault{409, "VERSION_CONFLICT", "This product changed. Reload and review before saving."}
}

var errAuth = &fault{401, "AUTH_REQUIRED", "Please log in again."}
var errNotFound = &fault{404, "PRODUCT_NOT_FOUND", "Product not found."}

func text(s string, max int) bool {
	return utf8.ValidString(s) && utf8.RuneCountInString(s) > 0 && utf8.RuneCountInString(s) <= max && !strings.ContainsRune(s, 0)
}
func validate(in Input, action string) (Product, error) {
	var p Product
	if action == "create" || action == "save" {
		if in.Name == nil || in.Category == nil || in.ShelfID == nil || in.Aliases == nil {
			return p, invalid()
		}
		p.Name = strings.TrimSpace(*in.Name)
		p.Category = strings.TrimSpace(*in.Category)
		p.ShelfID = *in.ShelfID
		if !text(p.Name, 120) || !text(p.Category, 80) || !idPattern.MatchString(p.ShelfID) || len(*in.Aliases) > 20 {
			return p, invalid()
		}
		p.Aliases = make([]Alias, 0, len(*in.Aliases))
		seen := map[string]bool{}
		for _, a := range *in.Aliases {
			a.Text = strings.TrimSpace(a.Text)
			if !text(a.Text, 120) || (a.Language != "en-US" && a.Language != "th-TH" && a.Language != "zh-CN" && a.Language != "ja-JP") {
				return p, invalid()
			}
			key := a.Language + "/" + importer.Normalize(a.Text)
			if seen[key] {
				return p, invalid()
			}
			seen[key] = true
			p.Aliases = append(p.Aliases, a)
		}
	} else if in.Name != nil || in.Category != nil || in.ShelfID != nil || in.Aliases != nil {
		return p, invalid()
	}
	if action == "create" {
		if in.ID == nil || !idPattern.MatchString(*in.ID) || in.ExpectedVersion != nil {
			return p, invalid()
		}
		p.ID = *in.ID
	} else if in.ID != nil || in.ExpectedVersion == nil || *in.ExpectedVersion < 1 {
		return p, invalid()
	}
	return p, nil
}

// Reject duplicate keys, unknown fields, null top-level objects and trailing JSON.
func decode(body []byte, value any) error {
	if len(body) == 0 || len(body) > 16<<10 || !utf8.Valid(body) {
		return invalid()
	}
	d := json.NewDecoder(bytes.NewReader(body))
	d.UseNumber()
	var walk func() error
	walk = func() error {
		t, e := d.Token()
		if e != nil {
			return e
		}
		delim, ok := t.(json.Delim)
		if !ok {
			return nil
		}
		switch delim {
		case '{':
			seen := map[string]bool{}
			for d.More() {
				k, e := d.Token()
				if e != nil {
					return e
				}
				key, ok := k.(string)
				if !ok || seen[key] {
					return errors.New("duplicate field")
				}
				seen[key] = true
				if e = walk(); e != nil {
					return e
				}
			}
		case '[':
			for d.More() {
				if e := walk(); e != nil {
					return e
				}
			}
		default:
			return errors.New("unexpected delimiter")
		}
		_, e = d.Token()
		return e
	}
	if err := walk(); err != nil {
		return invalid()
	}
	if bytes.TrimSpace(body)[0] != '{' {
		return invalid()
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(value); err != nil {
		return invalid()
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return invalid()
	}
	return nil
}
