package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/apaichon/prompt-shop/internal/backoffice"
	"github.com/apaichon/prompt-shop/internal/config"
	"github.com/apaichon/prompt-shop/internal/platform/database"
	"github.com/apaichon/prompt-shop/internal/platform/httpserver"
	"github.com/gofiber/fiber/v2"
)

func main() { os.Exit(run()) }
func run() int {
	cfg, err := config.Load()
	if err != nil {
		log.Print(err)
		return 1
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	pool, err := database.Open(ctx, cfg.DatabaseURL, 2)
	if err != nil {
		log.Print("database configuration invalid")
		return 1
	}
	defer pool.Close()
	checks := []httpserver.Check{httpserver.DatabaseCheck(pool)}
	if cfg.ReadinessMode == "full" {
		checks = append(checks, httpserver.SidecarCheck("http://127.0.0.1:8001/healthz"), httpserver.SidecarCheck("http://127.0.0.1:8003/healthz"))
	}
	deps := httpserver.Dependencies{Checks: checks, ReadinessMode: cfg.ReadinessMode}
	if cfg.BackofficeDatabaseURL != "" {
		adminPool, e := database.Open(ctx, cfg.BackofficeDatabaseURL, 2)
		if e != nil {
			log.Print("backoffice database configuration invalid")
			return 1
		}
		defer adminPool.Close()
		admin, e := backoffice.New(backoffice.NewRepository(adminPool), backoffice.Config{Origin: cfg.PortalOrigin, PasswordHash: cfg.MaintainerHash})
		if e != nil {
			log.Print("backoffice configuration invalid")
			return 1
		}
		deps.Register = admin.Register
		deps.Checks = append(deps.Checks, adminPool.Ping)
	} else {
		deps.Register = func(r fiber.Router) {
			r.All("/api/backoffice/*", func(c *fiber.Ctx) error {
				return httpserver.Error(c, 503, "DEPENDENCY_UNAVAILABLE", "Backoffice is not configured.", true)
			})
		}
	}
	if cfg.StaticDir != "" {
		assets, e := os.OpenRoot(cfg.StaticDir)
		if e != nil {
			log.Print("static portal unavailable")
			return 1
		}
		defer assets.Close()
		if _, e = assets.Stat("index.html"); e != nil {
			log.Print("static portal unavailable")
			return 1
		}
		deps.Static = assets.FS()
	}
	app := httpserver.New(deps)
	stopped := make(chan error, 1)
	go func() { stopped <- app.Listen(cfg.ListenAddress) }()
	log.Printf("server starting; readiness_scope=%s", cfg.ReadinessMode)
	select {
	case err := <-stopped:
		if err != nil {
			log.Print("server listener failed")
			return 1
		}
	case <-ctx.Done():
		if err := app.ShutdownWithTimeout(5 * time.Second); err != nil {
			log.Print("server shutdown deadline reached")
			return 1
		}
	}
	return 0
}
