-- LOCAL DISPOSABLE DEVELOPMENT ONLY. Never execute against Cloud SQL.
-- Apply roles.sql first; production LOGIN passwords come from Secret Manager.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='prompt_shop_reader') THEN
  CREATE ROLE prompt_shop_reader LOGIN PASSWORD 'local-reader-only';
 END IF;
END $$;
GRANT prompt_shop_public TO prompt_shop_reader;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='prompt_shop_ticket') THEN
  CREATE ROLE prompt_shop_ticket LOGIN PASSWORD 'local-ticket-only';
 END IF;
END $$;
GRANT prompt_shop_voice TO prompt_shop_ticket;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='prompt_shop_admin') THEN
  CREATE ROLE prompt_shop_admin LOGIN PASSWORD 'local-admin-only';
 END IF;
END $$;
GRANT prompt_shop_backoffice TO prompt_shop_admin;
