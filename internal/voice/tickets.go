package voice

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Ticket struct {
	SessionID, Language string
	ExpiresAt           time.Time
}
type TicketStore interface {
	Issue(context.Context, string, string, Ticket) error
	Consume(context.Context, string) (Ticket, error)
}
type PostgresTickets struct{ Pool *pgxpool.Pool }

func (p PostgresTickets) Issue(ctx context.Context, hash, previousHash string, t Ticket) error {
	ctx, cancel := context.WithTimeout(ctx, 750*time.Millisecond)
	defer cancel()
	tx, err := p.Pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if previousHash != "" {
		if _, err = tx.Exec(ctx, `UPDATE voice_tickets SET consumed_at=now() WHERE token_hash=$1 AND consumed_at IS NULL`, previousHash); err != nil {
			return err
		}
	}
	if _, err = tx.Exec(ctx, `INSERT INTO voice_tickets(token_hash,session_id,language,expires_at) VALUES($1,$2,$3,now()+interval '30 seconds')`, hash, t.SessionID, t.Language); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
func (p PostgresTickets) Consume(ctx context.Context, hash string) (Ticket, error) {
	ctx, cancel := context.WithTimeout(ctx, 750*time.Millisecond)
	defer cancel()
	var t Ticket
	err := p.Pool.QueryRow(ctx, `UPDATE voice_tickets SET consumed_at=now() WHERE token_hash=$1 AND consumed_at IS NULL AND expires_at>now() RETURNING session_id,language,expires_at`, hash).Scan(&t.SessionID, &t.Language, &t.ExpiresAt)
	return t, err
}

// Purge is an operator maintenance operation, not granted to the admission role.
func (p PostgresTickets) Purge(ctx context.Context) error {
	if p.Pool == nil {
		return errors.New("database unavailable")
	}
	_, err := p.Pool.Exec(ctx, `DELETE FROM voice_tickets WHERE expires_at < now()-interval '1 day'`)
	return err
}
