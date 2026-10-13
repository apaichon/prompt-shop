package security

import "testing"

func TestRedactTextRemovesCredentialValues(t *testing.T) {
	input := `postgres://writer:super-secret@db/monti password=hunter2 token=abc123 authorization=Bearer abc`
	got := RedactText(input)
	for _, forbidden := range []string{"super-secret", "hunter2", "abc123", "Bearer abc"} {
		if contains(got, forbidden) {
			t.Fatalf("redacted text contains %q: %s", forbidden, got)
		}
	}
}

func TestRedactTextKeepsSafeContext(t *testing.T) {
	got := RedactText(`security configuration: JWT_SECRET must be at least 32 bytes`)
	if got != `security configuration: JWT_SECRET must be at least 32 bytes` {
		t.Fatalf("safe context changed: %s", got)
	}
}

func contains(value, needle string) bool {
	for i := 0; i+len(needle) <= len(value); i++ {
		if value[i:i+len(needle)] == needle {
			return true
		}
	}
	return false
}
