#!/usr/bin/env sh
# Postgres backup for the restore drill. Usage: ./deploy/backup.sh [output-dir]
set -eu
OUT=${1:-./backups}
mkdir -p "$OUT"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "${POSTGRES_USER:-nomax}" -d "${POSTGRES_DB:-nomax}" -Fc \
  > "$OUT/nomax-$STAMP.dump"
echo "wrote $OUT/nomax-$STAMP.dump"
