# Production deploy (Phase 9)

Iranian VPS, Docker Compose, Caddy automatic HTTPS.

```bash
cp .env.prod.example .env.prod
# edit DOMAIN, POSTGRES_PASSWORD, JWT_SECRET
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api \
  python -m app.cli create-superadmin --phone 09123456789 --name "Super Admin"
```

## Backup and restore from the dashboard

Superadmins can use `/admin/backups` to create, download, delete and restore
portable SQL backups. Files are stored in the `backups` Compose volume at
`/data/backups`. Restores require typing `RESTORE`, take an automatic safety
backup first and run in a single transaction.

The `worker` service creates one automatic dump every day at 03:00 Tehran
(`BACKUP_DAILY_*`). Manual and automatic backups are gzipped and uploaded to
the private Arvan bucket (`S3_BUCKET_PRIVATE`, or `BACKUP_S3_BUCKET`) under
`BACKUP_S3_PREFIX`; the newest `BACKUP_KEEP_REMOTE=30` objects are retained.
Set `S3_ACCESS_KEY`, `S3_SECRET_KEY` and the bucket variables in `.env.prod`.
The dashboard's «آرشیو در S3» action retries any failed/missing uploads.

`deploy/backup.sh` remains available for an independent custom-format dump and
restore drill. If the legacy `nomax-backup.timer` is installed on an older
server, disable it so it does not run alongside the built-in daily job.

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
