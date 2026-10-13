// Package httpserver owns shared public router wiring. Feature packages register
// routes through a constructor callback, before the JSON 404 fallback.
package httpserver

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"net/http"
	"time"

	"github.com/apaichon/prompt-shop/migrations"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Check func(context.Context) error
type Dependencies struct {
	Checks        []Check
	ReadinessMode string
	Register      func(fiber.Router)
}
type ErrorBody struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	Retryable bool   `json:"retryable"`
}
type ErrorEnvelope struct {
	Error     ErrorBody `json:"error"`
	RequestID string    `json:"request_id"`
}

func Error(c *fiber.Ctx, status int, code, msg string, retryable bool) error {
	return c.Status(status).JSON(ErrorEnvelope{ErrorBody{code, msg, retryable}, c.GetRespHeader("X-Request-ID")})
}
func New(d Dependencies) *fiber.App {
	app := fiber.New(fiber.Config{DisableStartupMessage: true, BodyLimit: 16 << 10, ReadTimeout: 5 * time.Second, WriteTimeout: 5 * time.Second, IdleTimeout: 60 * time.Second, ErrorHandler: func(c *fiber.Ctx, err error) error {
		status := 500
		code, msg := "INTERNAL_ERROR", "request failed"
		var fe *fiber.Error
		if errors.As(err, &fe) {
			switch fe.Code {
			case 400:
				status = 400
				code = "INVALID_REQUEST"
				msg = "invalid request"
			case 413:
				status = 413
				code = "MESSAGE_TOO_LARGE"
				msg = "request exceeds limit"
			case 404:
				status = 404
				code = "NOT_FOUND"
				msg = "route not found"
			}
		}
		return Error(c, status, code, msg, status >= 500)
	}})
	app.Use(func(c *fiber.Ctx) error {
		var id [16]byte
		if _, err := rand.Read(id[:]); err != nil {
			return err
		}
		c.Set("X-Request-ID", hex.EncodeToString(id[:]))
		c.Set("Cache-Control", "no-store")
		c.Set("X-Content-Type-Options", "nosniff")
		// Do not reflect client request IDs or log request bodies/URLs/headers.
		return c.Next()
	})
	app.Use(recover.New())
	app.Get("/healthz", func(c *fiber.Ctx) error { return c.JSON(fiber.Map{"status": "ok"}) })
	app.Get("/readyz", func(c *fiber.Ctx) error {
		c.Set("X-Readiness-Scope", d.ReadinessMode)
		ctx, cancel := context.WithTimeout(c.UserContext(), 1500*time.Millisecond)
		defer cancel()
		if len(d.Checks) == 0 {
			return c.Status(503).JSON(fiber.Map{"status": "not_ready"})
		}
		for _, check := range d.Checks {
			if err := check(ctx); err != nil {
				return c.Status(503).JSON(fiber.Map{"status": "not_ready"})
			}
		}
		return c.JSON(fiber.Map{"status": "ready"})
	})
	if d.Register != nil {
		d.Register(app)
	}
	app.Use(func(c *fiber.Ctx) error { return Error(c, 404, "NOT_FOUND", "route not found", false) })
	return app
}
func DatabaseCheck(pool *pgxpool.Pool) Check {
	return func(parent context.Context) error {
		ctx, cancel := context.WithTimeout(parent, 750*time.Millisecond)
		defer cancel()
		var ready bool
		err := pool.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version=$1) AND (SELECT count(*) FROM schema_migrations)=1 AND EXISTS(SELECT 1 FROM stores s JOIN map_nodes n ON n.store_id=s.id AND n.id=s.entrance_node_id WHERE s.id='demo-store' AND s.catalog_version>0 AND s.map_version>0) AND EXISTS(SELECT 1 FROM products WHERE store_id='demo-store') AND EXISTS(SELECT 1 FROM aisles WHERE store_id='demo-store')`, migrations.Version).Scan(&ready)
		if err != nil {
			return err
		}
		if !ready {
			return errors.New("foundation not initialized")
		}
		return nil
	}
}
func SidecarCheck(url string) Check {
	client := &http.Client{Timeout: 250 * time.Millisecond, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	return func(parent context.Context) error {
		ctx, cancel := context.WithTimeout(parent, 250*time.Millisecond)
		defer cancel()
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return err
		}
		resp, err := client.Do(req)
		if err != nil {
			return err
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			return errors.New("sidecar not ready")
		}
		return nil
	}
}
