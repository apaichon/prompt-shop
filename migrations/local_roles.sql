-- LOCAL DISPOSABLE DEVELOPMENT ONLY. Never execute against Cloud SQL.
-- Apply roles.sql first; production LOGIN passwords come from Secret Manager.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='prompt_shop_reader') THEN
  CREATE ROLE prompt_shop_reader LOGIN PASSWORD 'local-reader-only';
 END IF;
END $$;
GRANT prompt_shop_public TO prompt_shop_reader;
