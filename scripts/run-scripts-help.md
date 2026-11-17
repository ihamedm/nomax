# Running one-off scripts

These scripts import the `app` package and must run inside the API container
(working directory `/app`), not on the VPS host. Every script is dry-run by
default; pass `--yes` to write.

Run these commands from the repo root on the VPS.

## Production (`docker-compose.prod.yml`)

The compose project is `nomax-prod`, so target the service by name (`api`)
rather than a container name.

### Archive an owner's businesses

Owner phone defaults to `09123456789`; override with `--phone`. Archived
businesses are hidden from public listings and from the admin list unless the
`بایگانی` filter is selected.

```bash
# 1. Copy the script into the running API container
docker compose -f docker-compose.prod.yml cp scripts/set_owner_businesses_pending.py api:/tmp/

# 2. Dry run: shows how many businesses the owner has, changes nothing
docker compose -f docker-compose.prod.yml exec api \
  python /tmp/set_owner_businesses_pending.py

# 3. Apply: archive all of that owner's businesses
docker compose -f docker-compose.prod.yml exec api \
  python /tmp/set_owner_businesses_pending.py --yes

# Optional: another phone number
docker compose -f docker-compose.prod.yml exec api \
  python /tmp/set_owner_businesses_pending.py --phone 09120000000 --yes
```

To bring an archived business back, set its status to pending or approved
from the admin edit form (or use the archived filter in the admin list).

### Clear all business descriptions

```bash
docker compose -f docker-compose.prod.yml cp scripts/clear_business_descriptions.py api:/tmp/

docker compose -f docker-compose.prod.yml exec api \
  python /tmp/clear_business_descriptions.py          # dry run

docker compose -f docker-compose.prod.yml exec api \
  python /tmp/clear_business_descriptions.py --yes    # apply
```

### Import Behbahan businesses

Needs the CSV/image bundle on the VPS. Copy it into the container first, then
run in batches (`--dry-run` first).

```bash
docker compose -f docker-compose.prod.yml cp scripts/import_behbahan_businesses.py api:/tmp/
docker compose -f docker-compose.prod.yml cp /path/to/import-data api:/tmp/import-data

docker compose -f docker-compose.prod.yml exec api \
  python /tmp/import_behbahan_businesses.py \
    --csv /tmp/import-data/businesses.csv \
    --root /tmp/import-data \
    --limit 10 --dry-run

docker compose -f docker-compose.prod.yml exec api \
  python /tmp/import_behbahan_businesses.py \
    --csv /tmp/import-data/businesses.csv \
    --root /tmp/import-data \
    --count 25
```

## Local (`docker-compose.yml`)

Same commands with the local compose file; the API container is `nomax-api`.

```bash
docker cp scripts/set_owner_businesses_pending.py nomax-api:/tmp/
docker exec nomax-api python /tmp/set_owner_businesses_pending.py
docker exec nomax-api python /tmp/set_owner_businesses_pending.py --yes

docker cp scripts/clear_business_descriptions.py nomax-api:/tmp/
docker exec nomax-api python /tmp/clear_business_descriptions.py
docker exec nomax-api python /tmp/clear_business_descriptions.py --yes
```

## After running

Scripts write straight to the database. To verify from the host:

```bash
docker compose -f docker-compose.prod.yml exec db \
  psql -U nomax -d nomax -c \
  "SELECT b.id, b.name, b.status
     FROM businesses b
     JOIN users u ON u.id = b.owner_id
    WHERE u.phone = '09123456789';"
```

`sync-env.sh` is a host-side helper for syncing `.env` values; it is not a
Python maintenance script. Run it directly on the VPS with `bash`.
