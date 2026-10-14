-- Operator-run after migrations. NOLOGIN roles contain no credentials.
-- Cloud SQL operator needs CREATEROLE; map separate LOGINs to these roles.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='prompt_shop_public') THEN CREATE ROLE prompt_shop_public NOLOGIN; END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='prompt_shop_backoffice') THEN CREATE ROLE prompt_shop_backoffice NOLOGIN; END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='prompt_shop_voice') THEN CREATE ROLE prompt_shop_voice NOLOGIN; END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO prompt_shop_public,prompt_shop_backoffice,prompt_shop_voice;
GRANT SELECT ON schema_migrations,stores,aisles,map_nodes,map_edges,shelves,products,product_aliases TO prompt_shop_public,prompt_shop_backoffice;
GRANT INSERT,UPDATE ON products TO prompt_shop_backoffice;
GRANT INSERT,UPDATE,DELETE ON product_aliases,maintainer_sessions TO prompt_shop_backoffice;
GRANT SELECT ON maintainer_sessions,catalog_audit TO prompt_shop_backoffice;
GRANT INSERT ON catalog_audit TO prompt_shop_backoffice;
GRANT UPDATE(catalog_version) ON stores TO prompt_shop_backoffice;
GRANT USAGE ON SEQUENCE catalog_audit_id_seq TO prompt_shop_backoffice;
GRANT SELECT,INSERT,UPDATE,DELETE ON voice_tickets TO prompt_shop_voice;
-- Retention DELETE on catalog_audit belongs to an operator job, not public traffic.
