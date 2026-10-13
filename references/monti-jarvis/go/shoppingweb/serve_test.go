package shoppingweb

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHandlerServesAssetsAndSPAFallback(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "index.html"), []byte("shopping-index"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "app.js"), []byte("shopping-asset"), 0o600); err != nil {
		t.Fatal(err)
	}
	handler := Handler(root)

	for _, path := range []string{"/", "/stores/cotton-house", "/stores/cotton-house/orders/order-1"} {
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest(http.MethodGet, path, nil))
		if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), "shopping-index") {
			t.Fatalf("path %s status=%d body=%q", path, response.Code, response.Body.String())
		}
	}

	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/app.js", nil))
	if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), "shopping-asset") {
		t.Fatalf("asset status=%d body=%q", response.Code, response.Body.String())
	}
}

func TestHandlerMissingBuildIsActionable(t *testing.T) {
	response := httptest.NewRecorder()
	Handler(filepath.Join(t.TempDir(), "missing")).ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/", nil))
	if response.Code != http.StatusServiceUnavailable || !strings.Contains(response.Body.String(), "make shopping-web") {
		t.Fatalf("status=%d body=%q", response.Code, response.Body.String())
	}
}
