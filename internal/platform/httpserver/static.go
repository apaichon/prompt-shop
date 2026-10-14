package httpserver

import (
	"github.com/gofiber/fiber/v2"
	"io/fs"
	"mime"
	"path"
	"strings"
)

// Static serves only the capability-bounded build FS supplied by the server.
// APIs, sockets and private routes never receive an HTML fallback.
func Static(assets fs.FS) fiber.Handler {
	return func(c *fiber.Ctx) error {
		p := c.Path()
		for _, prefix := range []string{"/api", "/ws", "/internal", "/healthz", "/readyz"} {
			if p == prefix || strings.HasPrefix(p, prefix+"/") {
				return c.Next()
			}
		}
		if c.Method() != fiber.MethodGet && c.Method() != fiber.MethodHead {
			return c.Next()
		}
		name := strings.TrimPrefix(p, "/")
		if name == "" {
			name = "index.html"
		}
		if !fs.ValidPath(name) {
			return c.Next()
		}
		for _, segment := range strings.Split(name, "/") {
			if strings.HasPrefix(segment, ".") {
				return c.Next()
			}
		}
		file, err := fs.ReadFile(assets, name)
		if err != nil {
			if strings.HasPrefix(name, "_app/") || path.Ext(name) != "" {
				return c.Next()
			}
			name = "index.html"
			file, err = fs.ReadFile(assets, name)
			if err != nil {
				return c.Next()
			}
		}
		contentType := mime.TypeByExtension(path.Ext(name))
		if contentType == "" {
			contentType = "application/octet-stream"
		}
		c.Set("Content-Type", contentType)
		if strings.HasPrefix(name, "_app/immutable/") {
			c.Set("Cache-Control", "public, max-age=31536000, immutable")
		}
		if c.Method() == fiber.MethodHead {
			return c.SendStatus(200)
		}
		return c.Send(file)
	}
}
