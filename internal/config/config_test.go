package config

import "testing"

func TestVoiceRequiresSeparateCredentialsAndRejectsCloudHTTP(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://reader:example@localhost/test")
	t.Setenv("PUBLIC_ORIGIN", "http://localhost:8080")
	t.Setenv("VOICE_ENABLED", "true")
	t.Setenv("TICKET_DATABASE_URL", "")
	t.Setenv("ADK_BRIDGE_SECRET", "")
	t.Setenv("K_SERVICE", "")
	if _, err := Load(); err == nil {
		t.Fatal("voice started without its private configuration")
	}
	t.Setenv("TICKET_DATABASE_URL", "postgres://ticket:example@localhost/test")
	t.Setenv("ADK_BRIDGE_SECRET", "0123456789012345678901234567890123456789")
	t.Setenv("VOICE_ALLOW_LOCAL_HTTP", "true")
	if cfg, err := Load(); err != nil || !cfg.VoiceEnabled || !cfg.VoiceAllowLocalHTTP {
		t.Fatal("complete local voice configuration rejected", err)
	}
	t.Setenv("K_SERVICE", "cloud-service")
	if _, err := Load(); err == nil {
		t.Fatal("cloud HTTP development accepted")
	}
}

func TestConfiguration(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://reader:example@localhost/test")
	t.Setenv("READINESS_MODE", "")
	t.Setenv("PORT", "")
	t.Setenv("K_SERVICE", "")
	c, err := Load()
	if err != nil || c.ReadinessMode != "full" || c.ListenAddress != ":8080" {
		t.Fatal(c, err)
	}
	t.Setenv("READINESS_MODE", "foundation")
	t.Setenv("K_SERVICE", "cloud-service")
	if _, err = Load(); err == nil {
		t.Fatal("cloud foundation bypass accepted")
	}
	t.Setenv("K_SERVICE", "")
	t.Setenv("PORT", "wrong")
	if _, err = Load(); err == nil {
		t.Fatal("invalid port accepted")
	}
}

func TestBackofficeConfigIsAllOrNothing(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://example")
	t.Setenv("PUBLIC_ORIGIN", "https://portal.test")
	t.Setenv("ADMIN_PASSWORD_HASH", "")
	t.Setenv("BACKOFFICE_DATABASE_URL", "")
	if _, err := Load(); err != nil {
		t.Fatal("voice origin alone must not enable backoffice")
	}
	t.Setenv("BACKOFFICE_DATABASE_URL", "postgres://admin")
	if _, err := Load(); err == nil {
		t.Fatal("partial configuration must fail")
	}
	t.Setenv("ADMIN_PASSWORD_HASH", "opaque-config-test")
	if cfg, err := Load(); err != nil || cfg.BackofficeDatabaseURL == "" {
		t.Fatal("complete configuration rejected")
	}
}
