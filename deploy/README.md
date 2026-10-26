# Production deploy (Phase 9)

Iranian VPS, Docker Compose, Caddy automatic HTTPS.

```bash
cp .env.prod.example .env.prod
# edit DOMAIN, POSTGRES_PASSWORD, JWT_SECRET
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api \
  python -m app.cli create-superadmin --phone 09123456789 --name "Super Admin"
```

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
