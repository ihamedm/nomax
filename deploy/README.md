# Production deploy (Phase 9)

Iranian VPS, Docker Compose, Caddy automatic HTTPS.

```bash
cp .env.prod.example .env.prod
# edit DOMAIN, POSTGRES_PASSWORD, JWT_SECRET
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api \
  python -m app.cli create-superadmin --phone 09123456789 --name "Super Admin"
```

## Squashed migration baseline

The development chain (`0001`–`0023`) was replaced by a single baseline. A
database stamped with an old revision cannot be upgraded: the API container runs
`alembic upgrade head` on boot and exits with
`Can't locate revision identified by '0023'`. Beta data is disposable, so rebuild
the schema instead of restoring it (create a backup first if you want a copy):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --force-recreate api
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api \
  python -m app.cli seed-categories
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api \
  python -m app.cli create-superadmin --phone 09123456789 --name "Super Admin"
```

`DROP SCHEMA public CASCADE` also removes the PostGIS extension; the baseline
recreates it. The Compose `POSTGRES_USER` is a superuser, so
`CREATE EXTENSION postgis` succeeds.

## Backup and restore from the dashboard

Superadmins can use `/admin/backups` to create, download, delete and restore
portable SQL backups. Files are stored in the `backups` Compose volume at
`/data/backups`. Restores require typing `RESTORE`, take an automatic safety
backup first and run in a single transaction.

The `worker` service creates one automatic dump every day at 03:00 Tehran
(`BACKUP_DAILY_*`). Manual and automatic backups are created as `.sql.gz` and
the same archive is uploaded to the private Arvan bucket (`S3_BUCKET_PRIVATE`, or `BACKUP_S3_BUCKET`) under
`BACKUP_S3_PREFIX`; the newest `BACKUP_KEEP_REMOTE=30` objects are retained.
Set `S3_ACCESS_KEY`, `S3_SECRET_KEY` and the bucket variables in `.env.prod`.
The dashboard's «آرشیو در S3» action retries any failed/missing uploads.

`deploy/backup.sh` remains available for an independent custom-format dump and
restore drill. If the legacy `nomax-backup.timer` is installed on an older
server, disable it so it does not run alongside the built-in daily job.

## Optional Laya category suggestions (temporarily disabled)

Laya is disabled for the beta: production runs with `LAYA_ENABLED=false` and no
sidecar, so the wizard uses the manual category picker. The implementation is
kept for future development.

To disable it on an existing server (this is already the default):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile laya rm -sf laya
# set LAYA_ENABLED=false in .env.prod, then recreate the API
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d api
```

The business wizard can suggest a category and subcategory from the title and
description. A high-precision Persian alias layer handles obvious cases; Laya
votes on ambiguous categories and subcategories. Laya runs in a separate
CPU-only container so the API image does not grow by PyTorch and the model.
The first start downloads the multilingual checkpoint (about 650 MB) into the
`laya_models` volume.

To re-enable it:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml   --profile laya up -d laya
# then set LAYA_ENABLED=true in .env.prod and recreate the API
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d api
```

Give the container at least 2 GB of RAM, and set `LAYA_THREADS` to the number
of physical CPU cores available (default 2). `/health` on the sidecar reports
readiness. If it is missing or slow, the API returns `status=unavailable` and
the owner uses the manual picker; no form submission is blocked. The `Laya`
suggestion is labelled as experimental in the UI.

## Restore drill

```bash
./deploy/backup.sh backups
cat backups/nomax-*.dump | docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U nomax -d nomax --clean --if-exists
```

## Observability (self-hosted)

- **GlitchTip** and **Uptime Kuma** run as separate Compose stacks on the same
  VPS (kept out of this file so the app stack stays small).
- Point the API at GlitchTip with `SENTRY_DSN` once the SDK is added; uptime
  checks hit `https://$DOMAIN/api/v1/...` and `GET /health`.
