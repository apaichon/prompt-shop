package config

import "testing"

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
