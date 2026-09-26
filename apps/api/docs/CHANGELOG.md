\# Changelog

## M37 Phase 2-A1 — InvitationService

Workspace invitations with hash-only token storage, single-use
acceptance, expiry, revocation, and members.max enforcement at
accept time.

### Added

- `app/domain/invitation.py` — token generation / hashing,
  state computation (pending / accepted / revoked / expired),
  `INVITABLE_ROLES` (admin / member / viewer — never owner).
- `app/services/memberships.py` — `require_minimum_role`,
  `ensure_member_quota`, `add_or_reactivate_member`.
- `app/services/invitations.py` — `create_invitation`,
  `accept_invitation`, `revoke_invitation`, `list_invitations`.
- 9 new AppError subclasses for invitation / membership
  semantics.

### Security

- Raw token never persisted: only `sha256(raw).hexdigest()`.
- Token is `secrets.token_urlsafe(32)`.
- Single-use: concurrent accepts serialized by
  `SELECT ... FOR UPDATE` on the invitation row.
- Expiration (410) and revocation (410) enforced.
- Acceptance requires the authenticated user's email to match
  the invitation's (403).
- Role escalation blocked: `owner` cannot be invited.

### Quota semantics

- Creating an invitation does **not** consume a member slot.
  Otherwise an owner on the free plan (members.max = 1) could
  never invite anyone.
- Accepting an invitation **does** enforce `members.max`,
  under a per-workspace advisory lock so concurrent accepts
  cannot overrun.

### Audit

- `MEMBER_INVITED`
- `INVITATION_ACCEPTED` with `outcome=created|reactivated`

### Tests

- `tests/services/test_m37_invitations.py` — 17 tests
  covering role gating, token security, idempotency,
  expiration, revocation, email match, member quota,
  concurrency.

### Not yet implemented (planned for later phases)

- Invitation delivery (email)
- `POST /api/v1/workspaces/{id}/invitations` route
- `POST /api/v1/invitations/{token}/accept` route

\## M36 — Production Foundation



Infrastructure, security, reliability, observability, and production

hardening. No business semantics changed. No new database migration.



\### Configuration



\- Added M36 configuration block: log format, CORS, trusted hosts,

&#x20; trusted proxies, request ID, body limit, rate limits, readiness/

&#x20; shutdown timeouts, metrics/tracing toggles, secret backend, DB pool

&#x20; settings, backup settings, audit toggle.

\- Production fail-closed validation: rejects `DEBUG=true`, wildcard

&#x20; CORS, weak/default `JWT\_SECRET\_KEY`.

\- `.env.example` and variant templates added at repo root and API.



\### Secrets



\- Added `app.core.secrets.SecretResolver` (env-backed default).

\- No secret leaks in repr / model\_dump / logs / responses.



\### Request correlation



\- Added `RequestIdMiddleware` (pure-ASGI, exactly one response header).

\- Request ID is set in a contextvar for handlers, exception handlers,

&#x20; and structured logs.



\### Structured logging



\- Added JSON output mode with safe serialization (UUID / datetime /

&#x20; Enum / arbitrary objects).

\- Added redaction layer for bearer tokens, DB URLs, and known

&#x20; sensitive field names.

\- Never logs Authorization headers, passwords, API keys, DB URLs

&#x20; with credentials, manuscript content, evidence packets.



\### Structured errors



\- Unified error envelope: `{"error": {"code", "message",

&#x20; "request\_id", ...}}`.

\- HTTPException and RequestValidationError preserved with `detail`.

\- SQLAlchemy classified: OperationalError → 503,

&#x20; IntegrityError → 409, other → 500.

\- `Retry-After` header + `retry\_after` body field on 429.



\### HTTP hardening



\- BodyLimitMiddleware: strict `\[0-9]+` Content-Length validation,

&#x20; duplicate headers must match byte-identically, buffered body replay

&#x20; so an oversized request never starts endpoint execution.

\- GlobalRateLimitMiddleware: per-IP sliding-window limiter with

&#x20; bounded cardinality (`max\_keys`), LRU eviction, OPTIONS bypass.

\- Trusted-proxy-aware client-IP resolution. XFF is only trusted when

&#x20; the direct peer belongs to `TRUSTED\_PROXIES`.

\- CORS and TrustedHost fully configuration-driven.



\### Rate limiting



\- Provider-neutral `RateLimitBackend` interface.

\- In-memory implementation documented as per-process only.

\- Per-user / per-endpoint dependencies via `rate\_limit\_deps`.

\- Test isolation via autouse fixture.



\### Health \& readiness



\- `/health/live` — process liveness only.

\- `/health/ready` — configuration + database + queue.

\- Reuses the existing `health\_engine` (NullPool, connect\_timeout=3).

\- No internals leaked in the response.



\### Observability



\- `app.observability.metrics` — provider-neutral MetricsBackend,

&#x20; InMemory implementation for tests, no vendor dependency.

\- `app.observability.tracing` — provider-neutral Tracer, Noop default.



\### Worker hardening



\- `threading.Event`-based shutdown with immediate wake.

\- Per-job `WorkerStats` tracking; double-finish idempotent.

\- `active\_jobs` invariant: `== len(active\_job\_ids)` at all times.

\- `\_execute` accounting wrapped in `finally`.

\- `app.workers.health.collect\_health` — internal diagnostic.



\### Storage



\- Download route now emits `Content-Length` matching the recorded

&#x20; file size.



\### Audit



\- `app.services.audit.emit\_audit` — structured, allowlisted, redacted

&#x20; audit events routed through the existing logger. No new table.



\### Retention



\- `app.services.retention.RetentionPolicy` contract.

\- Default `NoopRetentionPolicy` never deletes anything.



\### Operations



\- `app/db/session.py`: bounded pool (pool\_size, max\_overflow,

&#x20; pool\_timeout, pool\_recycle, pool\_pre\_ping, connect\_timeout,

&#x20; statement\_timeout).

\- Lifespan disposes engine pools independently and exception-safely.



\### Container \& CI



\- Multi-stage `Dockerfile`, non-root user, `HEALTHCHECK`, pinned base.

\- `.dockerignore`.

\- `docker-compose.yml` for local Postgres + pgvector + API.

\- `.github/workflows/ci.yml`: lint, typecheck, tests, migration gate

&#x20; (upgrade / downgrade / re-upgrade), smoke test, docker build.



\### Backup \& restore



\- `scripts/backup\_db.py` — pg\_dump wrapper with sha256 + metadata

&#x20; sidecar + retention.

\- `scripts/verify\_backup.py` — sha256 + size + TOC check.

\- `scripts/restore\_db.py` — safe restore with `--dry-run` and

&#x20; `--yes` guard.

\- `docs/backup-restore.md`.



\### Docs



\- `docs/production.md`

\- `docs/security.md`

\- `docs/operations.md`

\- `docs/backup-restore.md`

\- `docs/dependencies.md`

\- `docs/CHANGELOG.md` (this file)

\- `README.md` (revised)



\### Security \& regression tests



\- Cross-tenant isolation across M24-M35 resources.

\- Request ID never used as authentication.

\- Concurrency smoke tests.

\- Failure scenarios: DB down, invalid config, rate-limit backend

&#x20; unreachable, stale worker reclaim.

\- M24-M35 route registration smoke test.

\- Logging privacy tests.



\### Out of scope for M36



\- No SaaS billing, workspaces, or subscription logic.

\- No frontend.

\- No paid API integrations.

\- No real secret manager backend.

\- No distributed rate-limit backend (Redis).

\- No tracing/metrics vendor SDK.

\- No new database migration.

