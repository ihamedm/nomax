# ADR 0002 — OTP authentication, RBAC and the dev OTP viewer

- **Status:** Accepted and implemented (Phase 1)
- **Date:** 2026-10-26

## Context

NOMAX is phone-first (no passwords for customers). Admins need scoped access,
and developers need to log in without waiting for Mellipayamak KYC or a real
SMS. A development shortcut must not become a production back door.

## Decisions

### OTP

- Six-digit codes, 120s TTL, 3 requests/hour per phone and per IP, 5 verify
  attempts per code. Codes are single-use.
- Production stores an HMAC hash only. Non-production (`APP_ENV=local|test`)
  also mirrors the plaintext under `dev:otp:{phone}` for 120s.
- A successful verify creates the user as `customer`, marks the phone verified,
  and can attach a validated Iranian national ID. National IDs are unique and
  cannot be overwritten once set.
- Access tokens are short-lived JWTs. Refresh tokens rotate; replaying an
  already-used `jti` revokes the whole token family (theft detection).

### RBAC

- Roles: `customer`, `owner`, `admin`, `superadmin`.
- Granular permissions are a JSON list on the user and only apply to the
  `admin` role. Promotion to `admin` keeps the existing list; demotion to any
  other role clears it, so dormant grants never resurrect later. `has_permission`
  additionally refuses non-admin roles as defence in depth.
- `superadmin` is implicit-all. Only superadmins change roles/permissions.
- Permission codes live in one catalog (`app/core/permissions.py`); unknown
  codes are rejected with 422.
- Every role/permission change writes an `admin_audit_logs` row.
- A superadmin cannot demote themselves, and the last superadmin cannot be
  demoted.

### Dev OTP viewer

Triple guard:

1. Router is not mounted when `APP_ENV=production`.
2. `DEV_OTP_ENABLED` must be true.
3. Endpoint requires a superadmin token.

The admin UI shows live codes, their TTL, and a copy button. The login screen
dev-fill hint only appears when the OTP request response includes `dev_otp`,
which only happens in dev.

## Consequences

- The first superadmin is created by CLI (`python -m app.cli create-superadmin`),
  never seeded with a default password.
- Rotating `JWT_SECRET` invalidates all sessions; refresh families in Redis
  expire on their own.
- A production deploy with `DEV_OTP_ENABLED=true` still cannot reach the dev
  router because of the environment check.
