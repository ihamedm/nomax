# Deploy biznestly.ir on an Ubuntu VPS behind ArvanCloud CDN

End-to-end runbook for a single-VPS production deploy of the NOMAX stack
(FastAPI + PostGIS + Redis + React) with **Caddy** terminating TLS on the
origin and **ArvanCloud CDN** in front of it.

```
browser ──TLS──▶ ArvanCloud edge (biznestly.ir, Arvan cert, cache/WAF)
                      │  HTTPS, Host: biznestly.ir
                      ▼
                VPS :443  Caddy (Let's Encrypt cert)
                      │
                      ▼
                web :80   nginx  ──/api/*──▶ api:8001 ──▶ db / redis
                      └── SPA static files
uploads ──▶ ArvanCloud S3 (public bucket, optionally s3.biznestly.ir)
```

Everything is already wired in [`docker-compose.prod.yml`](../docker-compose.prod.yml);
this document is the command sequence plus the ArvanCloud panel settings that
the Compose file cannot cover.

---

## 0. Prerequisites

| Item | Value |
| --- | --- |
| OS | Ubuntu 22.04 or 24.04 LTS, root/sudo |
| Size | 2 vCPU, **4 GB RAM**, 40 GB SSD (2 GB works only with swap; the frontend build is memory-hungry) |
| Domain | `biznestly.ir`, nameservers pointed to ArvanCloud |
| ArvanCloud | CDN + DNS + Object Storage (S3) + API access key |
| SMS | Mellipayamak shared-service account with an approved OTP template (`SMS_OTP_BODY_ID`) |
| Repo | `git@github.com:ihamedm/nomax.git` (private → deploy key) |

Set these shell variables once and reuse them:

```bash
export APP_DIR=/opt/nomax
export DOMAIN=biznestly.ir
export VPS_IP=203.0.113.10          # ← your server's public IPv4
```

---

## 1. ArvanCloud DNS (before touching the server)

1. At your registrar, set the domain's nameservers to the two ArvanCloud
   nameservers shown under **ArvanCloud → DNS → Nameservers**
   (`ns1/ns2.arvancloud.ir` on most accounts). Propagation can take a few hours.
2. In **ArvanCloud → DNS → Records**, create:

| Type | Name | Value | Proxy (cloud) |
| --- | --- | --- | --- |
| A | `@` (`biznestly.ir`) | `$VPS_IP` | **Off for now** (step 5) |
| A | `www` | `$VPS_IP` | Off (optional, see Appendix C) |
| CNAME | `s3` (optional) | your Arvan S3 public endpoint | per Arvan docs |

Keep the proxy **off** until Caddy has obtained its certificate (step 4).
Otherwise the HTTP-01 challenge may be answered by the CDN instead of the
origin, and issuance fails.

Verify:

```bash
dig +short biznestly.ir          # must print the VPS IP
```

---

## 2. Bootstrap the VPS

SSH in as root (`ssh root@$VPS_IP`) and run:

```bash
apt-get update && apt-get -y upgrade
apt-get install -y ca-certificates curl gnupg git ufw fail2ban jq unzip htop unattended-upgrades
systemctl enable --now unattended-upgrades

# Docker Engine + Compose v2 from Docker's repository
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker compose version
```

> If `download.docker.com` is unreachable from your network, the distro packages
> are an acceptable substitute:
> `apt-get install -y docker.io docker-compose-v2`.

Timezone, swap and log rotation:

```bash
timedatectl set-timezone Asia/Tehran

# 4 GB swap: without it the Node/Vite build can be OOM-killed on a 2 GB VPS
fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-nomax.conf && sysctl -p /etc/sysctl.d/99-nomax.conf

# Cap Docker logs so a noisy container cannot fill the disk
cat >/etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
systemctl restart docker
```

Firewall — only SSH, HTTP and HTTPS are public. Postgres and Redis are not
published by Compose, so they are reachable only from the Docker network.

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
```

If your VPS provider has its own cloud firewall, open 80/443 there too.

### 2.1 Deploy user

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
# paste your laptop's public key:
echo 'ssh-ed25519 AAAA... you@laptop' > /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

# The app directory is created here, as root, so the deploy user owns it and
# never needs sudo for git/docker operations.
install -d -m 755 -o deploy -g deploy /opt/nomax
```

Test `ssh deploy@$VPS_IP` **before** hardening SSH:

```bash
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sshd -t && systemctl reload ssh
```

---

## 3. Check out the code and create `.env.prod`

As the `deploy` user (re-export the paths — shell variables do not survive
`su`/`ssh`):

```bash
export APP_DIR=/opt/nomax
export DOMAIN=biznestly.ir

ssh-keygen -t ed25519 -C "biznestly-vps" -N "" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```

`/opt/nomax` was already created for this user as root in §2.1.

Add that key in GitHub → repo **Settings → Deploy keys → Add deploy key**
(read-only). Then:

```bash
mkdir -p ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
git clone git@github.com:ihamedm/nomax.git "$APP_DIR"
cd "$APP_DIR"
```

Create the production env file (it is git-ignored):

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod

PG_PASS="$(openssl rand -hex 24)"
JWT="$(openssl rand -hex 48)"
sed -i "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" .env.prod
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" .env.prod
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" .env.prod
```

Then edit `nano .env.prod` and fill:

- **S3**: `S3_ENDPOINT_URL`, `S3_REGION` (match the Arvan account, e.g.
  `ir-thr-at1` or `ir-central1`), `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
  `S3_BUCKET_PUBLIC`, `S3_BUCKET_PRIVATE`, and optionally `S3_PUBLIC_URL`
  (e.g. `https://s3.biznestly.ir` if the public bucket has a custom domain).
- **SMS**: `SMS_USERNAME`, `SMS_PASSWORD`, `SMS_OTP_BODY_ID` from Mellipayamak.
  Leaving `SMS_PROVIDER=console` in production means **nobody can log in**
  (codes are neither sent nor returned).
- **Map**: `VITE_NESHAN_MAP_KEY` (web SDK key). It is baked into the bundle at
  build time; changing it requires rebuilding `web`.

In ArvanCloud → **Object Storage**, create the two buckets and an access key.
The public bucket must be publicly readable (the app also sets
`public-read` ACLs, `S3_PUBLIC_READ_ACL=true`).

Validate the file before starting anything:

```bash
cd "$APP_DIR"
docker compose --env-file .env.prod -f docker-compose.prod.yml config >/dev/null && echo "compose OK"
```

> Always pass `--env-file .env.prod -f docker-compose.prod.yml`. Without them
> Compose reads the development `.env` / `docker-compose.yml`.

Add a shell helper for the rest of the runbook:

```bash
cat >> ~/.bashrc <<'EOF'
dc() { docker compose --env-file /opt/nomax/.env.prod -f /opt/nomax/docker-compose.prod.yml "$@"; }
EOF
source ~/.bashrc
```

---

## 4. First start (with the CDN still off)

Build and start. The API container runs `alembic upgrade head` on boot, so a
fresh database is migrated automatically.

```bash
cd "$APP_DIR"
dc up -d --build
dc ps
```

The first build compiles the frontend and installs Python wheels; expect a few
minutes. Then watch Caddy obtain the Let's Encrypt certificate:

```bash
dc logs -f caddy | grep -Ei 'obtain|certificate|error'
```

Once it settles (`certificate obtained successfully`), verify the origin
directly:

```bash
curl -fsS --resolve biznestly.ir:443:127.0.0.1 https://biznestly.ir/health; echo
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' https://biznestly.ir/
```

### Seed the catalog and create the superadmin

```bash
dc exec api python -m app.cli seed-categories
dc exec api python -m app.cli create-superadmin --phone 09123456789 --name "Super Admin"
```

`create-superadmin` only creates/promotes the row; logging in still requires a
working SMS provider (or the console fallback described in §9).

---

## 5. Turn on the ArvanCloud CDN

Back in the ArvanCloud panel, with the origin already serving a valid
certificate:

1. **DNS** — enable the proxy (cloud toggle) on the `A @` record.
   `dig +short biznestly.ir` now returns ArvanCloud edge IPs, not `$VPS_IP`.
2. **SSL/TLS** —
   - Enable ArvanCloud's free certificate for `biznestly.ir` (and `www` if used).
   - Mode: **Full** (origin speaks HTTPS). **Do not use Flexible** — Caddy
     force-redirects HTTP to HTTPS, which causes a redirect loop.
   - Force HTTPS: on.
3. Confirm traffic flows through the edge:

```bash
curl -sSI https://biznestly.ir | grep -Ei 'server|ar-|cache'
```

> Browser ↔ Arvan is encrypted with Arvan's certificate; Arvan ↔ Caddy uses the
> Let's Encrypt certificate Caddy obtained in step 4.

### Certificate renewals

Caddy renews at ~2/3 of the certificate lifetime (around day 60). Renewal uses
the same HTTP-01 challenge, now through the CDN. Add a CDN rule so it always
reaches the origin:

- **Cache bypass** for path `/.well-known/acme-challenge/*` (never cache it,
  and do not cache 404s).

Then check monthly:

```bash
dc logs --since 720h caddy | grep -i 'renew'
echo | openssl s_client -servername biznestly.ir -connect 127.0.0.1:443 2>/dev/null \
  | openssl x509 -noout -dates
```

If renewals fail, either switch to DNS-01 (Appendix B) or run Caddy with a
self-signed internal certificate while Arvan keeps SSL mode Full (Appendix B,
last paragraph).

---

## 6. ArvanCloud CDN settings that matter for this app

Configure these in **ArvanCloud → CDN** (labels vary slightly per plan).

### Caching

| Path / type | Rule | Why |
| --- | --- | --- |
| `/api/*` | **Bypass cache** | Auth, OTP, mutations; a cached POST/JSON response is a data leak |
| `/uploads/*` | Bypass | Only used by the local-storage fallback |
| `/health`, `/ready` | Bypass | Uptime checks must hit the origin |
| `/.well-known/*` | Bypass | ACME renewals |
| `/admin/*` | Bypass | Superadmin UI must not be cached publicly |
| `/assets/*` | Cache 30–365 days | Vite emits content-hashed, immutable files |
| `*.html`, `/` | No cache (or purge on deploy) | Otherwise a new deploy keeps old hashes until the cache expires |

The origin already sends `Cache-Control: public, immutable` for `/assets/` and
`no-store` for `index.html`; the CDN rules are a second line of defence.

### Origin

- Protocol **HTTPS**, port **443**, Host/SNI `biznestly.ir`.
- Origin **IPv4** only if the VPS has no IPv6 address.
- Raise the **origin timeout** to ~120 s: database restore, backup sync and
  analytics endpoints can exceed short defaults.
- Raise the **request body limit** to at least **16 MB** (gallery images are
  capped at 5 MB in the API). Database *restore uploads* can be up to
  `BACKUP_MAX_UPLOAD_MB` (512 MB by default) — either raise the CDN limit,
  lower that variable, or restore from an S3 archive instead of uploading.

### Features to disable

- **Always Online / stale-on-error**: serves a cached 200 while the origin is
  down, which hides incidents and breaks the API.
- **Rocket-Loader-style JS rewriting / async JS**: breaks the React bundle.
- **Under Attack mode** during normal operation: it challenges API clients too.

### Optional (recommended)

- WAF enabled; rate-limit `/api/v1/auth/*`.
- HSTS at the edge once HTTPS is verified end to end.

---

## 7. Smoke test

```bash
curl -fsS https://biznestly.ir/health; echo
curl -fsS https://biznestly.ir/ready | jq
curl -fsS https://biznestly.ir/api/v1/categories | head -c 300; echo
curl -fsS -o /dev/null -w 'SPA %{http_code}\n' https://biznestly.ir/some/spa/route
```

Expected:

- `/health` → `{"data":{"status":"ok"}}`
- `/ready` → `status: ok`, with `database`, `redis`, `storage` all `ok`.
  `503` with `storage: error` means the S3 key/secret/bucket/region is wrong;
  the API itself is fine but uploads and backups will fail.
- `/api/v1/categories` → JSON with the seeded categories
- unknown SPA routes → `200` (index.html), not `404`
- `https://biznestly.ir/` opens the app, and an OTP login sends a real SMS

Check the API is not leaking dev OTPs (this sends a real SMS; the default
throttle is `OTP_RATE_LIMIT_PER_HOUR=3`, repeated calls return `429`):

```bash
curl -sS -X POST https://biznestly.ir/api/v1/auth/otp/request \
  -H 'content-type: application/json' -d '{"phone":"09123456789"}'
```

The response must **not** contain `dev_otp` in production.

---

## 8. Day-2 operations

### Logs and status

```bash
dc ps
dc logs -f --tail=200 api
dc logs --tail=200 caddy
dc exec caddy caddy validate --config /etc/caddy/Caddyfile
```

### Deploy an update

```bash
cd /opt/nomax
git pull --ff-only
dc build
dc up -d
dc ps
docker image prune -f
```

Migrations run automatically when the `api` container starts. If a migration
fails the new container exits and the site returns 502 until you roll back —
`dc logs api` shows the Alembic error.

### Rollback

```bash
cd /opt/nomax
git log --oneline -5
git checkout <known-good-sha>
dc build && dc up -d
```

Database migrations are forward-only; taking a backup (below) before a release
that includes a migration is mandatory.

### Backups

The `worker` container writes a gzip dump every day at 03:00 Tehran to the
`backups` volume and uploads it to the private Arvan bucket. Verify:

```bash
dc exec api ls -lh /data/backups
dc logs --tail=100 worker | grep -i backup
```

Manual dump (independent of the app):

```bash
dc exec -T db pg_dump -U nomax -d nomax -Fc > ~/nomax-$(date +%F).dump
```

Restore drill (from [`deploy/README.md`](../deploy/README.md)):

```bash
dc exec -T db pg_restore -U nomax -d nomax --clean --if-exists < ~/nomax-YYYY-MM-DD.dump
```

Store a copy off the VPS (`scp` it to your laptop or rely on the S3 archive).
A backup that has never been restored is not a backup.

### Monitoring

- Uptime check: `https://biznestly.ir/health` (and `/ready`).
- External certificate expiry check on `biznestly.ir` (Caddy + Arvan each have
  one).
- Disk space on `/` and on the Docker volumes: `df -h`, `docker system df`.
- `dc exec api ls /data/backups | wc -l` should grow daily.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| **502/504 from Arvan** | Origin down or TLS mismatch. `dc ps`, then `curl -fsS --resolve biznestly.ir:443:127.0.0.1 https://biznestly.ir/health`. If that works, the CDN's SSL mode or origin port is wrong. |
| **526 / certificate error at the edge** | Origin certificate missing/expired or SSL mode is Full-Strict with a hostname mismatch. `dc logs caddy`, `dc exec caddy caddy validate ...`, check `openssl ... -dates`. |
| **Redirect loop** | CDN SSL mode is Flexible while Caddy forces HTTPS. Set Full. |
| **413 on image upload** | nginx limit (16 MB here), CDN body limit, or the API's 5 MB cap. Check `dc logs web`. |
| **CORS error in the browser** | `DOMAIN` must equal the exact host used (`biznestly.ir`, no `www`). Change `.env.prod`, then `dc up -d api` (env changes require recreating the container). |
| **OTP request returns 503** | Mellipayamak rejected the credentials/template. `dc logs api` shows `SMS delivery failed`. |
| **Nobody can log in, no SMS** | `SMS_PROVIDER=console` in production. Either configure Mellipayamak, or (temporarily, server access required) read the code from Redis: `dc exec redis redis-cli GET "dev:otp:09xxxxxxxxx"`. |
| **Old UI after deploy** | `index.html` cached by the CDN. Purge the Arvan cache and check the no-cache rule. |
| **Certificate never issued** | DNS proxy still on, or port 80 blocked. `dig +short biznestly.ir`, `ufw status`, `dc logs caddy`. |
| **Build killed (OOM)** | Not enough RAM. Add swap, or `dc build api` / `dc build web` one at a time. |
| **Wrong client IP in audit logs** | Arvan is in front; see Appendix A. |

---

## Appendix A — real client IP behind ArvanCloud

The API derives the client address from the leftmost `X-Forwarded-For` entry
(`backend/app/api/v1/auth.py`) for audit rows and the per-IP OTP throttle. With
a CDN in front, that value is only trustworthy if the edge overwrites it, and a
client that sends its own `X-Forwarded-For` can otherwise influence it.

Caddy can sanitise the chain when it knows the proxy ranges. The block below is
a **template**: replace both placeholders with the CIDRs published at
<https://www.arvancloud.ir/en/ips>. It will not parse until you do, and the
ranges change over time, so re-check them periodically.

```
{
	servers {
		trusted_proxies static <arvan-ipv4-cidr> <arvan-ipv6-cidr>
		trusted_proxies_strict
	}
}

{$DOMAIN} {
	encode gzip zstd
	reverse_proxy web:80 {
		header_up X-Forwarded-For {client_ip}
	}
}
```

Apply with:

```bash
dc exec caddy caddy validate --config /etc/caddy/Caddyfile
dc exec caddy caddy reload --config /etc/caddy/Caddyfile
```

A stale or wrong range does not break traffic; it only changes which address
ends up in logs. Leaving this appendix out is acceptable for the beta — all
functional rate limits (per phone) still apply.

---

## Appendix B — DNS-01 certificates (optional, CDN-proof)

HTTP-01 through the CDN normally works, but DNS-01 removes the dependency
entirely. It needs a custom Caddy image because the ArvanCloud DNS module is
not in the stock image.

`deploy/caddy/Dockerfile`:

```dockerfile
FROM caddy:2-builder AS builder
RUN xcaddy build --with github.com/caddy-dns/arvancloud

FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

Caddyfile:

```
{
	acme_dns arvancloud {$ARVAN_API_KEY}
}

{$DOMAIN} {
	encode gzip zstd
	reverse_proxy web:80
}
```

Compose (`caddy` service): replace `image: caddy:2-alpine` with
`build: ./deploy/caddy` and add `ARVAN_API_KEY: ${ARVAN_API_KEY}` to its
environment. Create an API key in the Arvan panel with DNS edit permission, add
it to `.env.prod` (editor, not `echo` — it is a secret):

```bash
printf 'ARVAN_API_KEY=%s\n' 'paste-the-key-here' >> .env.prod
chmod 600 .env.prod
dc build caddy && dc up -d caddy
```

If Go module downloads are blocked from the VPS, skip this and keep HTTP-01.

**Last resort:** run Caddy with a self-signed origin certificate and keep Arvan
in Full mode:

```
{$DOMAIN} {
	tls internal
	encode gzip zstd
	reverse_proxy web:80
}
```

Traffic stays encrypted, but the CDN no longer verifies the origin identity.

---

## Appendix C — hardening extras

**`www`** — either don't publish it, or point it at the VPS and add to
`deploy/Caddyfile`:

```
www.{$DOMAIN} {
	redir https://{$DOMAIN}{uri} permanent
}
```

and add `"https://www.${DOMAIN}"` to `CORS_ORIGINS` in
`docker-compose.prod.yml` (the SPA on `www` would otherwise be rejected). Browsers
follow the redirect before the SPA loads, so CORS only matters if you serve the
app on `www` directly.

**Hide API docs** — they are public by default. Inside the `{$DOMAIN}` block of
`deploy/Caddyfile`:

```
@docs path /docs* /redoc* /openapi.json
respond @docs 404
```

**Origin lockdown** — ArvanCloud publishes its edge ranges; allowing only those
to 80/443 (via `ufw`/cloud firewall) blocks direct-to-origin scans. Keep a
break-glass path to the VPS (provider console) in case the list changes.

---

## Deployment checklist

- [ ] Arvan nameservers active; `A @` → VPS IP; proxy **off** for first issue
- [ ] Ubuntu updated; Docker + Compose v2; swap; Docker log rotation; ufw 22/80/443
- [ ] `deploy` user, SSH key login, password auth disabled
- [ ] Repo cloned to `/opt/nomax`; `.env.prod` chmod 600
- [ ] `DOMAIN`, random `POSTGRES_PASSWORD` / `JWT_SECRET` set
- [ ] Arvan S3 buckets + access key; `/ready` reports `storage: ok`
- [ ] Mellipayamak credentials; a real OTP arrives
- [ ] Caddy certificate obtained (`dc logs caddy`)
- [ ] Arvan proxy enabled; SSL mode **Full**; no redirect loop
- [ ] CDN: bypass `/api/*`, `/uploads/*`, `/.well-known/*`; no-cache HTML; long-cache `/assets/*`
- [ ] CDN origin timeout / body limit adjusted
- [ ] `seed-categories` + `create-superadmin` done
- [ ] `/health`, `/ready`, categories API, SPA routing all green
- [ ] No `dev_otp` in the `otp/request` response
- [ ] Daily backup visible in `/data/backups` and in the private S3 bucket
- [ ] Uptime monitor on `/health`; certificate expiry monitored

