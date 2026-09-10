#!/usr/bin/env bash
# Applies every migration in supabase/migrations in order.
#
#   ./scripts/migrate.sh                  -> uses DATABASE_URL from .env
#   ./scripts/migrate.sh postgres://...   -> uses the URL given
#
# Migrations are forward-only and each runs in a single transaction
# (ON_ERROR_STOP), so a failure leaves that migration fully unapplied.

set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  [ -f .env ] && { set -a; . ./.env; set +a; }
  TARGET="${DATABASE_URL:-}"
fi

if [ -z "$TARGET" ]; then
  echo "No target database."
  echo "Set DATABASE_URL in .env, or pass a connection string as the first argument."
  echo
  echo "Supabase: Project Settings -> Database -> Connection string -> URI"
  echo "Use the DIRECT connection on port 5432 (the 6543 pooler cannot run DDL)."
  exit 1
fi

echo "Applying migrations to ${TARGET%%:*}://…${TARGET##*@}"
for f in supabase/migrations/*.sql; do
  printf '  %-45s' "$(basename "$f")"
  if psql -v ON_ERROR_STOP=1 -q -d "$TARGET" -f "$f" >/tmp/spi-migrate.log 2>&1; then
    echo "ok"
  else
    echo "FAILED"
    sed 's/^/    /' /tmp/spi-migrate.log | head -20
    exit 1
  fi
done
echo "All migrations applied."
