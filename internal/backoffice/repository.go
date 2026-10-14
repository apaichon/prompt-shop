package backoffice

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"time"

	"github.com/apaichon/prompt-shop/internal/platform/importer"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Repository interface {
	Session(context.Context, string, time.Time) (Session, error)
	Rotate(context.Context, string, string, Session, time.Time) error
	Revoke(context.Context, string) error
	List(context.Context, Filter) (Page, error)
	Shelves(context.Context) ([]Shelf, error)
	Mutate(context.Context, string, time.Time, string, Input, string) (Product, error)
}
type Postgres struct{ pool *pgxpool.Pool }

func NewRepository(pool *pgxpool.Pool) *Postgres { return &Postgres{pool} }
func dbContext(ctx context.Context) (context.Context, context.CancelFunc) {
	return context.WithTimeout(ctx, 750*time.Millisecond)
}
func (r *Postgres) Session(parent context.Context, hash string, now time.Time) (Session, error) {
	ctx, cancel := dbContext(parent)
	defer cancel()
	var s Session
	err := r.pool.QueryRow(ctx, `SELECT expires_at,csrf_token FROM maintainer_sessions WHERE token_hash=$1 AND expires_at>$2`, hash, now).Scan(&s.ExpiresAt, &s.CSRFToken)
	if errors.Is(err, pgx.ErrNoRows) {
		return s, errAuth
	}
	return s, err
}
func (r *Postgres) Rotate(parent context.Context, oldHash, newHash string, s Session, now time.Time) error {
	ctx, cancel := dbContext(parent)
	defer cancel()
	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer rollback(tx)
	if _, err = tx.Exec(ctx, `DELETE FROM maintainer_sessions WHERE token_hash=$1 OR expires_at<=$2`, oldHash, now); err != nil {
		return err
	}
	if _, err = tx.Exec(ctx, `INSERT INTO maintainer_sessions(token_hash,csrf_token,expires_at) VALUES($1,$2,$3)`, newHash, s.CSRFToken, s.ExpiresAt); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
func (r *Postgres) Revoke(parent context.Context, hash string) error {
	ctx, cancel := dbContext(parent)
	defer cancel()
	_, err := r.pool.Exec(ctx, `DELETE FROM maintainer_sessions WHERE token_hash=$1`, hash)
	return err
}

const productColumns = `p.id,p.name,p.category,p.shelf_id,p.state,p.version,p.updated_at,COALESCE((SELECT jsonb_agg(jsonb_build_object('language',a.language,'text',a.alias) ORDER BY a.language,a.normalized_alias) FROM product_aliases a WHERE a.store_id=p.store_id AND a.product_id=p.id),'[]'::jsonb)`

func scanProduct(row pgx.Row) (Product, error) {
	var p Product
	var raw []byte
	err := row.Scan(&p.ID, &p.Name, &p.Category, &p.ShelfID, &p.State, &p.Version, &p.UpdatedAt, &raw)
	if err == nil {
		err = json.Unmarshal(raw, &p.Aliases)
	}
	return p, err
}

type cursor struct {
	Last  string `json:"last"`
	Q     string `json:"q"`
	State string `json:"state"`
}

func parseFilter(q, state, opaque string) (Filter, error) {
	q = strings.TrimSpace(q)
	if len(q) > 800 || !text(q, 200) && q != "" {
		return Filter{}, invalid()
	}
	if state != "" && state != "draft" && state != "published" && state != "archived" {
		return Filter{}, invalid()
	}
	f := Filter{Q: importer.Normalize(q), State: state}
	if opaque != "" {
		if len(opaque) > 1600 {
			return f, invalid()
		}
		raw, err := base64.RawURLEncoding.DecodeString(opaque)
		if err != nil {
			return f, invalid()
		}
		var c cursor
		if decode(raw, &c) != nil || !idPattern.MatchString(c.Last) || c.Q != f.Q || c.State != f.State {
			return f, invalid()
		}
		f.Last = c.Last
	}
	return f, nil
}
func (r *Postgres) List(parent context.Context, f Filter) (Page, error) {
	ctx, cancel := dbContext(parent)
	defer cancel()
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{IsoLevel: pgx.RepeatableRead, AccessMode: pgx.ReadOnly})
	if err != nil {
		return Page{}, err
	}
	defer rollback(tx)
	rows, err := tx.Query(ctx, `SELECT `+productColumns+` FROM products p WHERE p.store_id=$1 AND ($2='' OR strpos(lower(p.name),$2)>0 OR EXISTS(SELECT 1 FROM product_aliases a WHERE a.store_id=p.store_id AND a.product_id=p.id AND strpos(a.normalized_alias,$2)>0)) AND ($3='' OR p.state=$3) AND ($4='' OR p.id>$4) ORDER BY p.id LIMIT 51`, storeID, f.Q, f.State, f.Last)
	if err != nil {
		return Page{}, err
	}
	defer rows.Close()
	page := Page{Items: []Product{}}
	for rows.Next() {
		p, err := scanProduct(rows)
		if err != nil {
			return page, err
		}
		page.Items = append(page.Items, p)
	}
	if err = rows.Err(); err != nil {
		return page, err
	}
	rows.Close()
	if len(page.Items) > 50 {
		page.Items = page.Items[:50]
		raw, _ := json.Marshal(cursor{page.Items[49].ID, f.Q, f.State})
		s := base64.RawURLEncoding.EncodeToString(raw)
		page.NextCursor = &s
	}
	return page, tx.Commit(ctx)
}
func (r *Postgres) Shelves(parent context.Context) ([]Shelf, error) {
	ctx, cancel := dbContext(parent)
	defer cancel()
	rows, err := r.pool.Query(ctx, `SELECT s.id,s.label,a.id,a.label,s.map_node_id IS NOT NULL FROM shelves s JOIN aisles a ON a.store_id=s.store_id AND a.id=s.aisle_id WHERE s.store_id=$1 ORDER BY a.id,s.id`, storeID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Shelf{}
	for rows.Next() {
		var s Shelf
		if err = rows.Scan(&s.ID, &s.Label, &s.Aisle.ID, &s.Aisle.Label, &s.Mapped); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}
func (r *Postgres) Mutate(parent context.Context, hash string, now time.Time, id string, in Input, action string) (Product, error) {
	proposed, err := validate(in, action)
	if err != nil {
		return Product{}, err
	}
	ctx, cancel := dbContext(parent)
	defer cancel()
	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return Product{}, err
	}
	defer rollback(tx)
	// Lock the live session until commit: a completed logout cannot race a stale write.
	var allowed bool
	err = tx.QueryRow(ctx, `SELECT true FROM maintainer_sessions WHERE token_hash=$1 AND expires_at>$2 FOR SHARE`, hash, now).Scan(&allowed)
	if errors.Is(err, pgx.ErrNoRows) {
		return Product{}, errAuth
	}
	if err != nil {
		return Product{}, err
	}
	if err = importer.LockStore(ctx, tx, storeID); err != nil {
		return Product{}, err
	}
	if action == "create" {
		id = proposed.ID
	} else {
		previous, e := scanProduct(tx.QueryRow(ctx, `SELECT `+productColumns+` FROM products p WHERE p.store_id=$1 AND p.id=$2 FOR UPDATE`, storeID, id))
		if errors.Is(e, pgx.ErrNoRows) {
			return Product{}, errNotFound
		}
		if e != nil {
			return Product{}, e
		}
		if previous.Version != *in.ExpectedVersion {
			return Product{}, conflict()
		}
		if action != "save" {
			proposed = previous
		}
	}
	if action == "create" || action == "save" || action == "publish" {
		var exists bool
		err = tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM shelves s JOIN aisles a ON a.store_id=s.store_id AND a.id=s.aisle_id WHERE s.store_id=$1 AND s.id=$2)`, storeID, proposed.ShelfID).Scan(&exists)
		if err != nil {
			return Product{}, err
		}
		if !exists {
			return Product{}, invalid()
		}
	}
	if action == "publish" {
		english := false
		for _, a := range proposed.Aliases {
			if a.Language == "en-US" && text(a.Text, 120) {
				english = true
			}
		}
		if !english {
			return Product{}, invalid()
		}
		var mapped bool
		err = tx.QueryRow(ctx, `WITH RECURSIVE reachable(id) AS (SELECT entrance_node_id FROM stores WHERE id=$1 UNION SELECT CASE WHEN e.from_node_id=r.id THEN e.to_node_id ELSE e.from_node_id END FROM map_edges e JOIN reachable r ON e.from_node_id=r.id OR e.to_node_id=r.id WHERE e.store_id=$1) SELECT EXISTS(SELECT 1 FROM shelves s JOIN reachable r ON r.id=s.map_node_id WHERE s.store_id=$1 AND s.id=$2)`, storeID, proposed.ShelfID).Scan(&mapped)
		if err != nil {
			return Product{}, err
		}
		if !mapped {
			return Product{}, invalid()
		}
	}
	switch action {
	case "create":
		_, err = tx.Exec(ctx, `INSERT INTO products(store_id,id,name,category,shelf_id,state) VALUES($1,$2,$3,$4,$5,'draft')`, storeID, id, proposed.Name, proposed.Category, proposed.ShelfID)
	case "save":
		_, err = tx.Exec(ctx, `UPDATE products SET name=$3,category=$4,shelf_id=$5,state='draft',version=version+1,updated_at=now() WHERE store_id=$1 AND id=$2`, storeID, id, proposed.Name, proposed.Category, proposed.ShelfID)
	case "publish", "archive":
		state := "published"
		if action == "archive" {
			state = "archived"
		}
		_, err = tx.Exec(ctx, `UPDATE products SET state=$3,version=version+1,updated_at=now() WHERE store_id=$1 AND id=$2`, storeID, id, state)
	default:
		return Product{}, invalid()
	}
	if err != nil {
		var pge *pgconn.PgError
		if errors.As(err, &pge) && pge.Code == "23505" {
			return Product{}, &fault{409, "VERSION_CONFLICT", "That product ID already exists."}
		}
		return Product{}, err
	}
	if action == "create" || action == "save" {
		if _, err = tx.Exec(ctx, `DELETE FROM product_aliases WHERE store_id=$1 AND product_id=$2`, storeID, id); err != nil {
			return Product{}, err
		}
		for _, a := range proposed.Aliases {
			if _, err = tx.Exec(ctx, `INSERT INTO product_aliases(store_id,product_id,language,normalized_alias,alias) VALUES($1,$2,$3,$4,$5)`, storeID, id, a.Language, importer.Normalize(a.Text), a.Text); err != nil {
				return Product{}, err
			}
		}
	}
	p, err := scanProduct(tx.QueryRow(ctx, `SELECT `+productColumns+` FROM products p WHERE p.store_id=$1 AND p.id=$2`, storeID, id))
	if err != nil {
		return Product{}, err
	}
	if _, err = tx.Exec(ctx, `UPDATE stores SET catalog_version=catalog_version+1 WHERE id=$1`, storeID); err != nil {
		return Product{}, err
	}
	if _, err = tx.Exec(ctx, `INSERT INTO catalog_audit(store_id,product_id,action,product_version) VALUES($1,$2,$3,$4)`, storeID, id, action, p.Version); err != nil {
		return Product{}, err
	}
	return p, tx.Commit(ctx)
}

// Cleanup remains bounded even when the query context expired or transport stalled.
func rollback(tx pgx.Tx) {
	ctx, cancel := context.WithTimeout(context.Background(), 250*time.Millisecond)
	defer cancel()
	_ = tx.Rollback(ctx)
}
