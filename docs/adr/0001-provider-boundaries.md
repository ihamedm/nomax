# ADR 0001 — Runtime provider boundaries

- **Status:** Accepted (Phase 0)
- **Date:** 2026-10-26
- **Supersedes:** the VAPID / web-push / foreign-SaaS parts of `proposal.md`

## Context

NOMAX must run in Iran without runtime calls to foreign SaaS. Build-time
libraries are fine (they are bundled); runtime *services* are not. Each
external capability therefore sits behind a small adapter so providers can be
swapped without touching feature code.

## Decisions

### Object storage

- `StorageBackend` interface with `put`, `get_presigned_url`, `delete`.
- Production: ArvanCloud S3. Development/test: MinIO, or local disk for unit
  tests.
- Two buckets: `nomax-public` (business images, ads) and `nomax-private`
  (license scans). License keys are never serialized in public responses;
  admins receive short-lived presigned URLs.
- Arvan S3 is validated early for path-style addressing and presign-host
  differences versus MinIO. Do not assume AWS S3 behaviour.

### SMS / OTP

- `SmsProvider` interface. Production: Mellipayamak shared-service pattern
  (`bodyId`, pre-approved template). Development: console provider, no network.
- OTP delivery is synchronous (interactive flow): ~8s timeout, at most two
  attempts, `503 sms_provider_unavailable` on failure.
- Every provider attempt writes an `sms_logs` row (`sent` / `failed`, provider
  message id, error). A code is deleted from Redis if delivery fails.

### Push

- No web push, no VAPID, no service worker.
- Native Android (Capacitor wrapper planned) uses an Iranian provider behind
  `PushProvider`: Pushe, Najva, or Chabok. Development uses a log provider that
  writes `notification_deliveries`.
- Separate `DeviceToken` table (provider, token, platform, app version,
  `last_seen_at`).

### Maps

- Iranian provider (Neshan / Map.ir / Parsimap) behind a map adapter.
- The provider choice is confirmed in Phase 2; a self-hosted/Leaflet fallback
  stays possible. No Google Maps or Mapbox.

### Background jobs

- Redis + `arq` (one worker) is sufficient at the 5,000-user scale.
- Reliability comes from a Postgres `scheduled_jobs` outbox swept every 30s,
  not from Redis alone. Workers are idempotent through `idempotency_key`.
- OTP stays synchronous; quote dispatch, expiry and notifications are queued.

## Consequences

- Provider outages degrade one capability only and are visible through audit
  tables (`sms_logs`, `notification_deliveries`).
- Deployments can switch to an Arvan registry mirror by overriding image names
  (`MINIO_IMAGE`, `MINIO_MC_IMAGE`).
- Phase 3 must not expose a public serializer for license object keys.
