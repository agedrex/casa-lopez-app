#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [[ "$(node -p "require('./front/package.json').devDependencies.auth")" != "1.7.7" || \
      "$(node -p "require('./front/package.json').dependencies['better-auth']")" != "1.7.7" ]]; then
  echo "Better Auth and its CLI must both be pinned to 1.7.7." >&2
  exit 1
fi
node -e 'import("node:module").then(({ registerHooks }) => { if (typeof registerHooks !== "function") process.exit(1); })' || {
  echo "The PostgreSQL integration test requires Node.js 22.15 or newer." >&2
  exit 1
}

container_name="wo7-auth-postgres-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
generated_sql="${RUNNER_TEMP:-/tmp}/better-auth-public.sql"
rm -f "$generated_sql"
container_id=""

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm --force "$container_id" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

export POSTGRES_PASSWORD="$(openssl rand -hex 32)"
export BETTER_AUTH_SECRET="$(openssl rand -hex 32)"
export PGUSER=postgres
export PGDATABASE=postgres

container_id="$(docker run --detach --rm --name "$container_name" \
  --env POSTGRES_PASSWORD \
  --publish 127.0.0.1::5432 \
  postgres:18.6)"
export PGPASSWORD="$POSTGRES_PASSWORD"
unset POSTGRES_PASSWORD
export PGPORT="$(docker port "$container_id" 5432/tcp | sed 's/.*://')"
export PGHOST=127.0.0.1
export AUTH_DATABASE_URL="postgres://postgres:${PGPASSWORD}@127.0.0.1:${PGPORT}/postgres"
export BETTER_AUTH_URL="http://localhost:${PGPORT}"

ready=0
for attempt in $(seq 1 60); do
  if docker exec "$container_id" pg_isready --host 127.0.0.1 --username "$PGUSER" --dbname "$PGDATABASE" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "Temporary PostgreSQL did not become ready." >&2
  exit 1
fi

server_version="$(docker exec \
  --env PGPASSWORD \
  --env PGUSER \
  --env PGDATABASE \
  --env PGHOST=127.0.0.1 \
  "$container_id" psql --no-psqlrc --tuples-only --no-align \
  --command 'SHOW server_version')"
server_version_num="$(docker exec --env PGPASSWORD --env PGUSER --env PGDATABASE --env PGHOST=127.0.0.1 "$container_id" psql --no-psqlrc --tuples-only --no-align --command 'SHOW server_version_num')"
printf 'Temporary PostgreSQL server_version=%s\n' "$server_version"
if [[ "$server_version_num" != "180006" ]]; then
  echo "Temporary PostgreSQL must report server_version_num=180006." >&2
  exit 1
fi

assert_no_costs_objects() {
  local phase="$1"
  local costs_objects
  costs_objects="$(docker exec \
    --env PGPASSWORD \
    --env PGUSER \
    --env PGDATABASE \
    --env PGHOST=127.0.0.1 \
    "$container_id" psql --no-psqlrc --tuples-only --no-align \
    --command "SELECT 'schema:' || n.nspname FROM pg_catalog.pg_namespace AS n WHERE n.nspname = 'costos' UNION ALL SELECT n.nspname || '.' || c.relname FROM pg_catalog.pg_class AS c JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace WHERE c.relkind IN ('r', 'p') AND n.nspname = 'public' AND c.relname IN ('categoria', 'producto', 'etapa', 'material', 'proveedor', 'precio_material', 'tipo_cambio', 'parametro', 'cotizacion', 'cotizacion_linea', 'marca_calidad', 'taller', 'orden_fabricacion', 'precio_venta', 'venta', 'plantilla_linea') ORDER BY 1")"
  if [[ -n "$costs_objects" ]]; then
    printf 'Unexpected costs objects %s:\n%s\n' "$phase" "$costs_objects" >&2
    return 1
  fi
  printf 'No costs schema or costing tables found %s.\n' "$phase"
}

assert_no_costs_objects "before Better Auth setup"

pnpm --dir front exec auth generate --config ./lib/auth.cli.ts --output "$generated_sql" --yes >/dev/null

versioned_sql="front/db/better-auth-public.sql"
if [[ ! -f "$versioned_sql" ]]; then
  echo "Versioned Better Auth SQL is missing: $versioned_sql" >&2
  exit 1
fi
if ! cmp --silent "$generated_sql" "$versioned_sql"; then
  echo "Generated Better Auth SQL differs from the versioned schema." >&2
  exit 1
fi

docker exec --interactive \
  --env PGPASSWORD \
  --env PGUSER \
  --env PGDATABASE \
  --env PGHOST=127.0.0.1 \
  "$container_id" psql --no-psqlrc --set ON_ERROR_STOP=1 < "$versioned_sql" >/dev/null
pnpm --dir front exec auth check schema --config ./lib/auth.cli.ts >/dev/null
pnpm --dir front test:auth-schema
pnpm --dir front test:auth-postgres
assert_no_costs_objects "after Better Auth checks"
