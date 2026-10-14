package shoppingweb

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

// Handler serves the independently built Shopping SPA at the root of its own
// hostname. API and WebSocket paths are registered before this fallback by the
// Go server, keeping browser credentials same-origin in production.
func Handler(root string) http.Handler {
	root = filepath.Clean(root)
	if _, err := os.Stat(root); err != nil {
		return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`<!doctype html><html><body style="font-family:system-ui;padding:2rem">
<h1>Shopping web not built</h1>
<p>Run <code>make shopping-web</code> then restart the server.</p>
</body></html>`))
		})
	}

	index := filepath.Join(root, "index.html")
	fileServer := http.FileServer(http.Dir(root))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" || r.URL.Path == "/index.html" || !strings.Contains(filepath.Base(r.URL.Path), ".") {
			http.ServeFile(w, r, index)
			return
		}
		fileServer.ServeHTTP(w, r)
	})
}
