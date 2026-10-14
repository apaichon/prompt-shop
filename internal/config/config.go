package config

import (
	"fmt"
	"os"
	"strconv"
)

type Config struct{ DatabaseURL, ListenAddress, ReadinessMode string }

func Load() (Config, error) {
	c := Config{DatabaseURL: os.Getenv("DATABASE_URL"), ReadinessMode: os.Getenv("READINESS_MODE")}
	if c.DatabaseURL == "" {
		return c, fmt.Errorf("DATABASE_URL is required")
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	n, err := strconv.Atoi(port)
	if err != nil || n < 1 || n > 65535 {
		return c, fmt.Errorf("invalid PORT")
	}
	c.ListenAddress = ":" + port
	if c.ReadinessMode == "" {
		c.ReadinessMode = "full"
	}
	if c.ReadinessMode != "full" && c.ReadinessMode != "foundation" {
		return c, fmt.Errorf("READINESS_MODE must be full or foundation")
	}
	// Foundation mode is explicitly local and cannot be deployed on Cloud Run.
	if c.ReadinessMode == "foundation" && os.Getenv("K_SERVICE") != "" {
		return c, fmt.Errorf("foundation readiness is local-only")
	}
	return c, nil
}
