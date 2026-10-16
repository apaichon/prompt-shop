package config

import (
	"fmt"
	"os"
	"strconv"
)

type Config struct {
	DatabaseURL, ListenAddress, ReadinessMode, BackofficeDatabaseURL, PortalOrigin, MaintainerHash, StaticDir string
	TicketDatabaseURL, BridgeSecret                                                                           string
	VoiceEnabled, VoiceAllowLocalHTTP                                                                         bool
}

func Load() (Config, error) {
	c := Config{DatabaseURL: os.Getenv("DATABASE_URL"), ReadinessMode: os.Getenv("READINESS_MODE")}
	c.BackofficeDatabaseURL = os.Getenv("BACKOFFICE_DATABASE_URL")
	c.PortalOrigin = os.Getenv("PUBLIC_ORIGIN")
	c.MaintainerHash = os.Getenv("ADMIN_PASSWORD_HASH")
	c.StaticDir = os.Getenv("STATIC_DIR")
	c.TicketDatabaseURL = os.Getenv("TICKET_DATABASE_URL")
	c.BridgeSecret = os.Getenv("ADK_BRIDGE_SECRET")
	var err error
	if value := os.Getenv("VOICE_ENABLED"); value != "" {
		c.VoiceEnabled, err = strconv.ParseBool(value)
		if err != nil {
			return c, fmt.Errorf("invalid VOICE_ENABLED")
		}
	}
	if value := os.Getenv("VOICE_ALLOW_LOCAL_HTTP"); value != "" {
		c.VoiceAllowLocalHTTP, err = strconv.ParseBool(value)
		if err != nil {
			return c, fmt.Errorf("invalid VOICE_ALLOW_LOCAL_HTTP")
		}
	}
	if c.VoiceEnabled && (c.TicketDatabaseURL == "" || c.PortalOrigin == "" || len(c.BridgeSecret) < 32) {
		return c, fmt.Errorf("voice requires TICKET_DATABASE_URL, PUBLIC_ORIGIN and ADK_BRIDGE_SECRET")
	}
	if c.VoiceAllowLocalHTTP && os.Getenv("K_SERVICE") != "" {
		return c, fmt.Errorf("HTTP voice development is local-only")
	}
	if (c.BackofficeDatabaseURL != "" || c.MaintainerHash != "") && (c.BackofficeDatabaseURL == "" || c.PortalOrigin == "" || c.MaintainerHash == "") {
		return c, fmt.Errorf("backoffice requires BACKOFFICE_DATABASE_URL, PUBLIC_ORIGIN and ADMIN_PASSWORD_HASH")
	}
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
