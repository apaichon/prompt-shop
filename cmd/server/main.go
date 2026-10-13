package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/apaichon/prompt-shop/internal/config"
	"github.com/apaichon/prompt-shop/internal/platform/database"
	"github.com/apaichon/prompt-shop/internal/platform/httpserver"
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
	app := httpserver.New(httpserver.Dependencies{Checks: checks, ReadinessMode: cfg.ReadinessMode})
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
