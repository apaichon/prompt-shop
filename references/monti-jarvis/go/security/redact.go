package security

import (
	"regexp"
	"strings"
)

var (
	credentialURL = regexp.MustCompile(`(?i)([a-z][a-z0-9+.-]*://)([^/@\s:]+)(?::[^/@\s]*)?@`)
	jwtToken      = regexp.MustCompile(`\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b`)
	authHeader    = regexp.MustCompile(`(?i)(authorization\s*[:=]\s*)[^,}]+`)
	secretField   = regexp.MustCompile(`(?i)("?(?:password|secret|token|api[_-]?key|authorization|cookie|prompt|request[_-]?body)"?\s*[:=]\s*)("?)[^\s,}"']+`)
)

// RedactText removes common credential-bearing values before text is logged or
// returned in diagnostic output. It intentionally keeps field names and error
// codes so operators still have useful remediation context.
func RedactText(raw string) string {
	if strings.TrimSpace(raw) == "" {
		return raw
	}
	out := credentialURL.ReplaceAllString(raw, `${1}[REDACTED]@`)
	out = jwtToken.ReplaceAllString(out, "[REDACTED_JWT]")
	out = authHeader.ReplaceAllString(out, `${1}[REDACTED]`)
	out = secretField.ReplaceAllString(out, `${1}${2}[REDACTED]`)
	return out
}
