// Local QA fixture server only. Never included in cmd/server or deployment images.
package main

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"github.com/apaichon/prompt-shop/internal/backoffice"
	"github.com/apaichon/prompt-shop/internal/platform/httpserver"
	"github.com/apaichon/prompt-shop/internal/platform/importer"
	"github.com/apaichon/prompt-shop/migrations"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/bcrypt"
	"log"
	"math/big"
	"net"
	"os"
	"time"
)

func main() {
	if err := run(); err != nil {
		log.Print("QA fixture server failed")
		os.Exit(1)
	}
}
func run() error {
	ctx := context.Background()
	cfg, err := pgxpool.ParseConfig(os.Getenv("BACKOFFICE_TEST_DATABASE_URL"))
	if err != nil {
		return err
	}
	if cfg.ConnConfig.Database != "prompt_shop_task9" || cfg.ConnConfig.Host != "127.0.0.1" {
		return fmt.Errorf("requires local disposable prompt_shop_task9")
	}
	operator, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return err
	}
	defer operator.Close()
	if _, err = operator.Exec(ctx, `DROP SCHEMA public CASCADE; CREATE SCHEMA public`); err != nil {
		return err
	}
	if err = migrations.Apply(ctx, operator); err != nil {
		return err
	}
	file, err := os.Open("data/demo-store.json")
	if err != nil {
		return err
	}
	defer file.Close()
	if _, err = importer.Import(ctx, operator, file); err != nil {
		return err
	}
	roles, err := os.ReadFile("migrations/roles.sql")
	if err != nil {
		return err
	}
	if _, err = operator.Exec(ctx, string(roles)); err != nil {
		return err
	}
	if _, err = operator.Exec(ctx, `DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='prompt_shop_task9_admin') THEN CREATE ROLE prompt_shop_task9_admin LOGIN PASSWORD 'task9-admin-local-only'; END IF; END $$;GRANT prompt_shop_backoffice TO prompt_shop_task9_admin`); err != nil {
		return err
	}
	adminCfg := cfg.Copy()
	adminCfg.ConnConfig.User = "prompt_shop_task9_admin"
	adminCfg.ConnConfig.Password = "task9-admin-local-only"
	adminCfg.MaxConns = 2
	admin, err := pgxpool.NewWithConfig(ctx, adminCfg)
	if err != nil {
		return err
	}
	defer admin.Close()
	hash, err := bcrypt.GenerateFromPassword([]byte("task9-test-password-only"), 12)
	if err != nil {
		return err
	}
	api, err := backoffice.New(backoffice.NewRepository(admin), backoffice.Config{Origin: "https://127.0.0.1:4194", PasswordHash: string(hash)})
	if err != nil {
		return err
	}
	assets, err := os.OpenRoot("web/build")
	if err != nil {
		return err
	}
	defer assets.Close()
	app := httpserver.New(httpserver.Dependencies{Register: api.Register, Static: assets.FS(), ReadinessMode: "backoffice-fixture", Checks: []httpserver.Check{admin.Ping}})
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return err
	}
	template := &x509.Certificate{SerialNumber: big.NewInt(9), Subject: pkix.Name{CommonName: "Task 9 local QA"}, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(time.Hour), IPAddresses: []net.IP{net.ParseIP("127.0.0.1")}, KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		return err
	}
	keyDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		return err
	}
	certificate, err := tls.X509KeyPair(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}), pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: keyDER}))
	if err != nil {
		return err
	}
	listener, err := tls.Listen("tcp", "127.0.0.1:4194", &tls.Config{Certificates: []tls.Certificate{certificate}, MinVersion: tls.VersionTLS12})
	if err != nil {
		return err
	}
	defer listener.Close()
	fmt.Println("QA fixture ready at https://127.0.0.1:4194; local database and real backoffice API")
	return app.Listener(listener)
}
