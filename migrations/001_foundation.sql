CREATE DOMAIN entity_id AS text CHECK (VALUE ~ '^[a-z0-9-]{1,64}$');
CREATE TABLE stores (
 id entity_id PRIMARY KEY, name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
 catalog_version bigint NOT NULL DEFAULT 0 CHECK (catalog_version >= 0),
 map_version bigint NOT NULL DEFAULT 0 CHECK (map_version >= 0),
 map_width double precision NOT NULL CHECK (map_width > 0 AND map_width < 'Infinity'::float8),
 map_height double precision NOT NULL CHECK (map_height > 0 AND map_height < 'Infinity'::float8),
 entrance_node_id entity_id NOT NULL
);
CREATE TABLE aisles (
 store_id entity_id REFERENCES stores(id), id entity_id, label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 80),
 polygon jsonb NOT NULL CHECK (jsonb_typeof(polygon) = 'array' AND jsonb_array_length(polygon) BETWEEN 3 AND 64), PRIMARY KEY(store_id,id)
);
CREATE TABLE map_nodes (
 store_id entity_id REFERENCES stores(id), id entity_id, x double precision NOT NULL, y double precision NOT NULL,
 label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 80), PRIMARY KEY(store_id,id),
 CHECK (x >= 0 AND x < 'Infinity'::float8 AND y >= 0 AND y < 'Infinity'::float8)
);
ALTER TABLE stores ADD CONSTRAINT stores_entrance_fk FOREIGN KEY(id,entrance_node_id) REFERENCES map_nodes(store_id,id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE map_edges (
 store_id entity_id REFERENCES stores(id), from_node_id entity_id, to_node_id entity_id,
 weight double precision NOT NULL CHECK (weight > 0 AND weight < 'Infinity'::float8),
 PRIMARY KEY(store_id,from_node_id,to_node_id), CHECK (from_node_id < to_node_id),
 FOREIGN KEY(store_id,from_node_id) REFERENCES map_nodes(store_id,id), FOREIGN KEY(store_id,to_node_id) REFERENCES map_nodes(store_id,id)
);
CREATE INDEX map_edges_to_idx ON map_edges(store_id,to_node_id);
CREATE TABLE shelves (
 store_id entity_id REFERENCES stores(id), id entity_id, aisle_id entity_id NOT NULL,
 label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 80), map_node_id entity_id,
 x double precision NOT NULL, y double precision NOT NULL, PRIMARY KEY(store_id,id),
 FOREIGN KEY(store_id,aisle_id) REFERENCES aisles(store_id,id), FOREIGN KEY(store_id,map_node_id) REFERENCES map_nodes(store_id,id),
 CHECK (x >= 0 AND x < 'Infinity'::float8 AND y >= 0 AND y < 'Infinity'::float8)
);
CREATE TABLE products (
 store_id entity_id REFERENCES stores(id), id entity_id, name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
 category text NOT NULL CHECK (char_length(category) BETWEEN 1 AND 80), shelf_id entity_id NOT NULL,
 state text NOT NULL CHECK (state IN ('draft','published','archived')),
 version bigint NOT NULL DEFAULT 1 CHECK (version > 0), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(store_id,id), FOREIGN KEY(store_id,shelf_id) REFERENCES shelves(store_id,id)
);
CREATE INDEX products_state_shelf_idx ON products(store_id,state,shelf_id);
CREATE TABLE product_aliases (
 store_id entity_id, product_id entity_id, language text NOT NULL CHECK (language IN ('en-US','th-TH','zh-CN','ja-JP')),
 normalized_alias text NOT NULL CHECK (char_length(normalized_alias) BETWEEN 1 AND 360),
 alias text NOT NULL CHECK (char_length(alias) BETWEEN 1 AND 120), PRIMARY KEY(store_id,product_id,language,normalized_alias),
 FOREIGN KEY(store_id,product_id) REFERENCES products(store_id,id) ON DELETE CASCADE
);
CREATE INDEX aliases_lookup_idx ON product_aliases(store_id,language,normalized_alias text_pattern_ops);
CREATE TABLE import_batches (
 store_id entity_id REFERENCES stores(id), import_version entity_id, content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
 applied_at timestamptz NOT NULL DEFAULT now(), product_count integer NOT NULL CHECK (product_count >= 0), PRIMARY KEY(store_id,import_version)
);
CREATE TABLE maintainer_sessions (
 token_hash text PRIMARY KEY CHECK (token_hash ~ '^[a-f0-9]{64}$'), csrf_token text NOT NULL, expires_at timestamptz NOT NULL
);
CREATE INDEX maintainer_expiry_idx ON maintainer_sessions(expires_at);
CREATE TABLE voice_tickets (
 token_hash text PRIMARY KEY CHECK (token_hash ~ '^[a-f0-9]{64}$'), session_id text NOT NULL UNIQUE,
 language text NOT NULL, expires_at timestamptz NOT NULL, consumed_at timestamptz
);
CREATE INDEX voice_expiry_idx ON voice_tickets(expires_at);
CREATE TABLE catalog_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, store_id entity_id NOT NULL, product_id entity_id NOT NULL,
 action text NOT NULL CHECK (action IN ('create','save','publish','archive')), product_version bigint NOT NULL CHECK (product_version > 0),
 created_at timestamptz NOT NULL DEFAULT now(), actor text NOT NULL DEFAULT 'maintainer' CHECK (actor='maintainer'),
 FOREIGN KEY(store_id,product_id) REFERENCES products(store_id,id)
);
CREATE INDEX catalog_audit_created_idx ON catalog_audit(created_at);
