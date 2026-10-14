package importer

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"reflect"
	"sort"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Result struct {
	Status         string `json:"status"`
	ProductCount   int    `json:"product_count"`
	CatalogVersion int64  `json:"catalog_version"`
	MapVersion     int64  `json:"map_version"`
}

// LockStore must also be used by backoffice writers. Transaction-scoped, stable
// across processes; hash collisions only serialize unrelated stores.
func LockStore(ctx context.Context, tx pgx.Tx, storeID string) error {
	_, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtextextended($1, 0))`, storeID)
	return err
}
func Import(ctx context.Context, pool *pgxpool.Pool, r io.Reader) (Result, error) {
	var result Result
	b, raw, err := Decode(r)
	if err != nil {
		return result, err
	}
	if b.StoreID != StoreID {
		return result, invalid("store_id", "INVALID_STORE", "store_id must be demo-store")
	}
	if b.SchemaVersion != 1 {
		return result, invalid("schema_version", "INVALID_VERSION", "schema_version must be 1")
	}
	if !idPattern.MatchString(b.ImportVersion) {
		return result, invalid("import_version", "INVALID_ID", "invalid import version")
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return result, err
	}
	defer tx.Rollback(context.Background())
	if err = LockStore(ctx, tx, b.StoreID); err != nil {
		return result, err
	}
	hash := fmt.Sprintf("%x", sha256.Sum256(raw))
	var oldHash string
	err = tx.QueryRow(ctx, `SELECT content_sha256,product_count FROM import_batches WHERE store_id=$1 AND import_version=$2`, b.StoreID, b.ImportVersion).Scan(&oldHash, &result.ProductCount)
	if err == nil {
		if oldHash != hash {
			return result, invalid("import_version", "VERSION_CONFLICT", "import version already has different content")
		}
		err = tx.QueryRow(ctx, `SELECT catalog_version,map_version FROM stores WHERE id=$1`, b.StoreID).Scan(&result.CatalogVersion, &result.MapVersion)
		result.Status = "unchanged"
		return result, err
	}
	if err != pgx.ErrNoRows {
		return result, err
	}
	old, err := load(ctx, tx, b.StoreID)
	if err != nil {
		return result, err
	}
	merged := merge(old, b)
	if err = validate(b, merged); err != nil {
		return result, err
	}
	mapChanged := !reflect.DeepEqual(old.Store, merged.Store) || !reflect.DeepEqual(old.Aisles, merged.Aisles) || !reflect.DeepEqual(old.Nodes, merged.Nodes) || !reflect.DeepEqual(old.Edges, merged.Edges) || !reflect.DeepEqual(old.Shelves, merged.Shelves)
	changed := mapChanged
	if old.Store == nil {
		_, err = tx.Exec(ctx, `INSERT INTO stores(id,name,map_width,map_height,entrance_node_id) VALUES($1,$2,$3,$4,$5)`, b.StoreID, merged.Store.Name, merged.Store.Width, merged.Store.Height, merged.Store.Entrance)
	} else if !reflect.DeepEqual(old.Store, merged.Store) {
		_, err = tx.Exec(ctx, `UPDATE stores SET name=$2,map_width=$3,map_height=$4,entrance_node_id=$5 WHERE id=$1`, b.StoreID, merged.Store.Name, merged.Store.Width, merged.Store.Height, merged.Store.Entrance)
	}
	if err != nil {
		return result, err
	}
	for _, a := range b.Aisles {
		polygon, _ := json.Marshal(a.Polygon)
		_, err = tx.Exec(ctx, `INSERT INTO aisles(store_id,id,label,polygon) VALUES($1,$2,$3,$4) ON CONFLICT(store_id,id) DO UPDATE SET label=EXCLUDED.label,polygon=EXCLUDED.polygon`, b.StoreID, a.ID, a.Label, polygon)
		if err != nil {
			return result, err
		}
	}
	for _, n := range b.Nodes {
		_, err = tx.Exec(ctx, `INSERT INTO map_nodes(store_id,id,x,y,label) VALUES($1,$2,$3,$4,$5) ON CONFLICT(store_id,id) DO UPDATE SET x=EXCLUDED.x,y=EXCLUDED.y,label=EXCLUDED.label`, b.StoreID, n.ID, n.X, n.Y, n.Label)
		if err != nil {
			return result, err
		}
	}
	for _, e := range b.Edges {
		if e.From > e.To {
			e.From, e.To = e.To, e.From
		}
		_, err = tx.Exec(ctx, `INSERT INTO map_edges(store_id,from_node_id,to_node_id,weight) VALUES($1,$2,$3,$4) ON CONFLICT(store_id,from_node_id,to_node_id) DO UPDATE SET weight=EXCLUDED.weight`, b.StoreID, e.From, e.To, e.Weight)
		if err != nil {
			return result, err
		}
	}
	for _, s := range b.Shelves {
		_, err = tx.Exec(ctx, `INSERT INTO shelves(store_id,id,aisle_id,label,map_node_id,x,y) VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(store_id,id) DO UPDATE SET aisle_id=EXCLUDED.aisle_id,label=EXCLUDED.label,map_node_id=EXCLUDED.map_node_id,x=EXCLUDED.x,y=EXCLUDED.y`, b.StoreID, s.ID, s.AisleID, s.Label, s.NodeID, s.X, s.Y)
		if err != nil {
			return result, err
		}
	}
	for _, p := range b.Products {
		previous, exists := old.Products[p.ID]
		if exists && sameProduct(previous, p) {
			continue
		}
		changed = true
		_, err = tx.Exec(ctx, `INSERT INTO products(store_id,id,name,category,shelf_id,state) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(store_id,id) DO UPDATE SET name=EXCLUDED.name,category=EXCLUDED.category,shelf_id=EXCLUDED.shelf_id,state=EXCLUDED.state,version=products.version+1,updated_at=now()`, b.StoreID, p.ID, p.Name, p.Category, p.ShelfID, p.State)
		if err != nil {
			return result, err
		}
		if _, err = tx.Exec(ctx, `DELETE FROM product_aliases WHERE store_id=$1 AND product_id=$2`, b.StoreID, p.ID); err != nil {
			return result, err
		}
		for _, a := range p.Aliases {
			_, err = tx.Exec(ctx, `INSERT INTO product_aliases(store_id,product_id,language,normalized_alias,alias) VALUES($1,$2,$3,$4,$5)`, b.StoreID, p.ID, a.Language, Normalize(a.Text), a.Text)
			if err != nil {
				return result, err
			}
		}
	}
	_, err = tx.Exec(ctx, `UPDATE stores SET catalog_version=catalog_version+$2,map_version=map_version+$3 WHERE id=$1`, b.StoreID, increment(changed), increment(mapChanged))
	if err != nil {
		return result, err
	}
	_, err = tx.Exec(ctx, `INSERT INTO import_batches(store_id,import_version,content_sha256,product_count) VALUES($1,$2,$3,$4)`, b.StoreID, b.ImportVersion, hash, len(b.Products))
	if err != nil {
		return result, err
	}
	err = tx.QueryRow(ctx, `SELECT catalog_version,map_version FROM stores WHERE id=$1`, b.StoreID).Scan(&result.CatalogVersion, &result.MapVersion)
	if err != nil {
		return result, err
	}
	result.Status = "applied"
	result.ProductCount = len(b.Products)
	return result, tx.Commit(ctx)
}
func increment(v bool) int {
	if v {
		return 1
	}
	return 0
}
func sameProduct(a, b Product) bool {
	a.Aliases = append([]Alias(nil), a.Aliases...)
	b.Aliases = append([]Alias(nil), b.Aliases...)
	less := func(a, b Alias) bool { return a.Language+"/"+a.Text < b.Language+"/"+b.Text }
	sort.Slice(a.Aliases, func(i, j int) bool { return less(a.Aliases[i], a.Aliases[j]) })
	sort.Slice(b.Aliases, func(i, j int) bool { return less(b.Aliases[i], b.Aliases[j]) })
	return reflect.DeepEqual(a, b)
}
func load(ctx context.Context, tx pgx.Tx, storeID string) (state, error) {
	s := emptyState()
	v := &Store{}
	err := tx.QueryRow(ctx, `SELECT name,map_width,map_height,entrance_node_id FROM stores WHERE id=$1`, storeID).Scan(&v.Name, &v.Width, &v.Height, &v.Entrance)
	if err == pgx.ErrNoRows {
		return s, nil
	}
	if err != nil {
		return s, err
	}
	s.Store = v
	queries := []struct {
		sql  string
		scan func(pgx.Rows) error
	}{
		{`SELECT id,label,polygon FROM aisles WHERE store_id=$1`, func(r pgx.Rows) error {
			var a Aisle
			var raw []byte
			if err := r.Scan(&a.ID, &a.Label, &raw); err != nil {
				return err
			}
			if err := json.Unmarshal(raw, &a.Polygon); err != nil {
				return err
			}
			s.Aisles[a.ID] = a
			return nil
		}},
		{`SELECT id,x,y,label FROM map_nodes WHERE store_id=$1`, func(r pgx.Rows) error {
			var n Node
			if err := r.Scan(&n.ID, &n.X, &n.Y, &n.Label); err != nil {
				return err
			}
			s.Nodes[n.ID] = n
			return nil
		}},
		{`SELECT from_node_id,to_node_id,weight FROM map_edges WHERE store_id=$1`, func(r pgx.Rows) error {
			var e Edge
			if err := r.Scan(&e.From, &e.To, &e.Weight); err != nil {
				return err
			}
			s.Edges[edgeKey(e)] = e
			return nil
		}},
		{`SELECT id,aisle_id,label,map_node_id,x,y FROM shelves WHERE store_id=$1`, func(r pgx.Rows) error {
			var sh Shelf
			if err := r.Scan(&sh.ID, &sh.AisleID, &sh.Label, &sh.NodeID, &sh.X, &sh.Y); err != nil {
				return err
			}
			s.Shelves[sh.ID] = sh
			return nil
		}},
		{`SELECT p.id,p.name,p.category,p.shelf_id,p.state,COALESCE((SELECT jsonb_agg(jsonb_build_object('language',a.language,'text',a.alias) ORDER BY a.language,a.normalized_alias) FROM product_aliases a WHERE a.store_id=p.store_id AND a.product_id=p.id),'[]'::jsonb) FROM products p WHERE p.store_id=$1`, func(r pgx.Rows) error {
			var p Product
			var raw []byte
			if err := r.Scan(&p.ID, &p.Name, &p.Category, &p.ShelfID, &p.State, &raw); err != nil {
				return err
			}
			if err := json.Unmarshal(raw, &p.Aliases); err != nil {
				return err
			}
			s.Products[p.ID] = p
			return nil
		}},
	}
	for _, q := range queries {
		rows, err := tx.Query(ctx, q.sql, storeID)
		if err != nil {
			return s, err
		}
		for rows.Next() {
			if err = q.scan(rows); err != nil {
				rows.Close()
				return s, err
			}
		}
		err = rows.Err()
		rows.Close()
		if err != nil {
			return s, err
		}
	}
	return s, nil
}
