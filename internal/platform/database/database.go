package database

import (
	"context"
	"github.com/jackc/pgx/v5/pgxpool"
	"time"
)

// Open returns a bounded pool. Credentials are never logged. Runtime public reads
// use a read-only principal; imports use a separately provisioned operator URL.
func Open(ctx context.Context, url string, max int32) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		return nil, err
	}
	cfg.MaxConns = max
	cfg.MinConns = 0
	cfg.MaxConnIdleTime = 5 * time.Minute
	cfg.ConnConfig.ConnectTimeout = 750 * time.Millisecond
	return pgxpool.NewWithConfig(ctx, cfg)
}
