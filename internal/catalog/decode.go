package catalog

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
)

const maxCustomerBody = 8 << 10

var (
	errInvalidJSON = errors.New("invalid json")
	errTooLarge    = errors.New("body too large")
)

func decodeJSON(body []byte, limit int, dest any) error {
	if len(body) > limit {
		return errTooLarge
	}
	if err := uniqueJSON(body); err != nil {
		return errInvalidJSON
	}
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.DisallowUnknownFields()
	if err := dec.Decode(dest); err != nil {
		return errInvalidJSON
	}
	if err := dec.Decode(&struct{}{}); err != io.EOF {
		return errInvalidJSON
	}
	return nil
}

func uniqueJSON(raw []byte) error {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	return walkJSON(dec)
}

func walkJSON(dec *json.Decoder) error {
	tok, err := dec.Token()
	if err != nil {
		return err
	}
	delim, ok := tok.(json.Delim)
	if !ok {
		return nil
	}
	switch delim {
	case '{':
		seen := map[string]bool{}
		for dec.More() {
			keyTok, err := dec.Token()
			if err != nil {
				return err
			}
			key, ok := keyTok.(string)
			if !ok || seen[key] {
				return errors.New("duplicate field")
			}
			seen[key] = true
			if err = walkJSON(dec); err != nil {
				return err
			}
		}
	case '[':
		for dec.More() {
			if err = walkJSON(dec); err != nil {
				return err
			}
		}
	default:
		return errors.New("unexpected delimiter")
	}
	_, err = dec.Token()
	return err
}
