#!/bin/sh
# Local PostgreSQL only; never uses OPERATOR_DATABASE_URL from the caller.
set -eu

action=${1:-help}
action=${action#infra-}
case "$action" in
    start|stop|restart|reset-data|status|logs) ;;
    *) printf '%s\n' 'Usage: make start|stop|restart|reset-data|status|logs' >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."
command -v rtk >/dev/null 2>&1 || { printf '%s\n' 'rtk is required.' >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { printf '%s\n' 'Docker with Compose is required.' >&2; exit 1; }
rtk proxy docker compose version >/dev/null
if ! rtk proxy docker info >/dev/null 2>&1; then
    printf '%s\n' 'Docker is not running. Start Docker Desktop (or your Docker daemon), then retry.' >&2
    exit 1
fi

# Copy once with private permissions; preserve an existing environment file.
if [ ! -f .env ]; then
    (umask 077; rtk proxy cp -n .env.example .env)
    printf '%s\n' 'Created .env from .env.example for local development.'
fi
set -a
. ./.env
set +a

POSTGRES_USER=${POSTGRES_USER:-prompt_shop_operator}
POSTGRES_DB=${POSTGRES_DB:-prompt_shop}
POSTGRES_PORT=${POSTGRES_PORT:-55432}
export POSTGRES_USER POSTGRES_DB POSTGRES_PORT
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"

compose() {
    # Stable project identity lets commands from this task worktree manage the
    # same local stack as docker compose from the main repository directory.
    rtk proxy docker compose --project-name prompt-shop --file compose.yaml --env-file .env "$@"
}

preflight_seed() {
    command -v go >/dev/null 2>&1 || { printf '%s\n' 'Go is required to migrate and seed local data.' >&2; exit 1; }
    command -v python3 >/dev/null 2>&1 || { printf '%s\n' 'Python 3 is required to construct the local database URL.' >&2; exit 1; }
    # Always derive a loopback operator URL from this local Compose setup.
    # Ignore any remote/operator URL in .env, including during reset-data.
    OPERATOR_DATABASE_URL=$(rtk proxy python3 -c '
import os
from urllib.parse import quote
port = int(os.environ.get("POSTGRES_PORT", "55432"))
if not 1 <= port <= 65535:
    raise SystemExit("POSTGRES_PORT must be between 1 and 65535")
user = quote(os.environ["POSTGRES_USER"], safe="")
password = quote(os.environ["POSTGRES_PASSWORD"], safe="")
database = quote(os.environ["POSTGRES_DB"], safe="")
print(f"postgres://{user}:{password}@127.0.0.1:{port}/{database}?sslmode=disable")
')
    export OPERATOR_DATABASE_URL
}

wait_for_db() {
    attempt=0
    until compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge 60 ]; then
            printf '%s\n' 'PostgreSQL did not become ready within 60 checks. Inspect make logs.' >&2
            return 1
        fi
        rtk proxy sleep 1
    done
}

seed_db() {
    rtk proxy env -u GOROOT go run ./cmd/import -migrate -file data/demo-store.json
    compose exec -T db sh -c 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < migrations/roles.sql
    compose exec -T db sh -c 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < migrations/local_roles.sql
}

case "$action" in
    start)
        preflight_seed
        compose up -d db
        wait_for_db
        seed_db
        printf '%s\n' 'Local PostgreSQL is ready; migrations, demo data and read-only login are initialized.'
        ;;
    stop)
        compose stop db
        ;;
    restart)
        compose up -d db
        compose restart db
        wait_for_db
        printf '%s\n' 'Local PostgreSQL restarted; existing data retained.'
        ;;
    reset-data)
        preflight_seed
        printf '%s\n' 'Deleting the prompt-shop Compose database volume and recreating local demo data.'
        compose down --volumes
        compose up -d db
        wait_for_db
        seed_db
        printf '%s\n' 'Local database reset to the demo seed. Custom products, sessions and database logins were removed.'
        ;;
    status) compose ps ;;
    logs) compose logs --follow db ;;
esac
