// Package migrations provides operator-only, serialized, additive migrations.
package migrations

import (
	"context"
	"crypto/sha256"
	_ "embed"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const Version = 1

//go:embed 001_foundation.sql
var foundation string

// Apply is deliberately never called by the public server.
func Apply(ctx context.Context, pool *pgxpool.Pool) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(context.Background())
	if _, err = tx.Exec(ctx, `SELECT pg_advisory_xact_lock(742190001)`); err != nil {
		return err
	}
	if _, err = tx.Exec(ctx, `CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())`); err != nil {
		return err
	}
	hash := fmt.Sprintf("%x", sha256.Sum256([]byte(foundation)))
	var old string
	err = tx.QueryRow(ctx, `SELECT sha256 FROM schema_migrations WHERE version=$1`, Version).Scan(&old)
	if err == nil {
		if old != hash {
			return fmt.Errorf("migration checksum mismatch")
		}
		return tx.Commit(ctx)
	}
	if err != pgx.ErrNoRows {
		return err
	}
	if _, err = tx.Exec(ctx, foundation); err != nil {
		return err
	}
	if _, err = tx.Exec(ctx, `INSERT INTO schema_migrations(version,sha256) VALUES($1,$2)`, Version, hash); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
