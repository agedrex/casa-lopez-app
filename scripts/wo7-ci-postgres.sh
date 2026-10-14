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
  postgres:17)"
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

pnpm --dir front exec auth generate --config ./lib/auth.cli.ts --output "$generated_sql" --yes >/dev/null

versioned_sql="front/db/better-auth-public.sql"
if [[ -f "$versioned_sql" ]]; then
  if ! cmp --silent "$generated_sql" "$versioned_sql"; then
    echo "Generated Better Auth SQL differs from the versioned schema." >&2
    exit 1
  fi
else
  mkdir -p front/db
  cp "$generated_sql" "$versioned_sql"
fi

docker exec --interactive \
  --env PGPASSWORD \
  --env PGUSER \
  --env PGDATABASE \
  --env PGHOST=127.0.0.1 \
  "$container_id" psql --no-psqlrc --set ON_ERROR_STOP=1 < "$generated_sql" >/dev/null
pnpm --dir front exec auth check schema --config ./lib/auth.cli.ts >/dev/null
pnpm --dir front test:auth-schema
pnpm --dir front test:auth-postgres
