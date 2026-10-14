package voice

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

// Epoch is server-owned; the public/private wire format follows TASK-0001.
type Epoch uint64

func (e Epoch) MarshalJSON() ([]byte, error) { return json.Marshal(fmt.Sprintf("turn-%d", e)) }
func (e *Epoch) UnmarshalJSON(raw []byte) error {
	var value string
	if err := json.Unmarshal(raw, &value); err != nil {
		return err
	}
	if !strings.HasPrefix(value, "turn-") {
		return fmt.Errorf("invalid turn")
	}
	n, err := strconv.ParseUint(strings.TrimPrefix(value, "turn-"), 10, 64)
	if err != nil || value != fmt.Sprintf("turn-%d", n) {
		return fmt.Errorf("invalid turn")
	}
	*e = Epoch(n)
	return nil
}
func parseEpoch(value string) Epoch {
	var e Epoch
	raw, _ := json.Marshal(value)
	_ = e.UnmarshalJSON(raw)
	return e
}
func generationID(e Epoch) string { return fmt.Sprintf("generation-%d", e) }
