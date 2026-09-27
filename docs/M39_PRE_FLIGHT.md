# Research-AI — M39 Pre-Flight / F00 Baseline

Date: 2026-09-27
Repository: mehrabja/research-ai
Branch: feature/m14-humanization
Baseline commit inspected: 106ca1fd2b5b1b86e4e9521ffa9c33f3d8ddfa91

## Scope

This pre-flight is a source-level repository inspection only. Runtime tests, migrations, startup checks, and external-provider smoke tests were intentionally not executed in F00, per implementation instruction.

Status vocabulary:
- Implemented: source code exists.
- Verified: not claimed unless runtime/test/integration evidence exists.
- Configured: real environment configuration is present and evidenced.
- Not Configured: integration exists only as a placeholder, fake provider, local implementation, or missing deployment configuration.
- Deferred: intentionally postponed.
- Known Limitation: confirmed limitation recorded from source inspection.

## M39 gate

**Implementation sweep completed; runtime verification remains separate.**

### Provider interfaces

Implemented:
- Generation provider protocol and typed error contract.
- Embedding provider protocol and typed error contract.
- Translation provider protocol and typed error contract.
- Detection provider protocol and typed error contract.
- Source/literature provider protocol and typed error contract.
- Billing provider protocol.

Not verified/configured:
- Central project-wide provider registry/resolver is now present in `apps/api/app/providers`.
- Generation/embedding/translation/detection/source factories now route through the registry.
- Ordered transient-failure fallback is supported through `PROVIDER_FALLBACKS`.
- Billing now declares `none`, `fake`, and `stripe`; Stripe adapter and webhook route are implemented.

### Resilience

Implemented:
- Provider-local retry/backoff exists for OpenAI generation and embeddings.
- Semantic Scholar adapter has retry/backoff and typed failure mapping.
- Durable job retry/reclaim primitives exist.

Known Limitation:
- Ordered cross-provider fallback is implemented for generation, embedding, translation, detection, and source discovery.

### Usage

Implemented:
- M37 `usage_events` model and idempotent workspace-scoped recorder.
- Metrics include: reports_created, jobs_enqueued, files_uploaded, storage_bytes, ai_generation_units, search_requests.
- Legacy provider-aware `usage_logs` remain in generation/embedding/translation paths.

Known Limitations:
- Storage aggregation is now enforced through workspace quota checks and active-byte aggregation.
- Provider operations now write authoritative workspace usage events; legacy usage logs remain as compatibility history.

### Billing

Implemented:
- Provider protocol.
- Subscription model.
- Subscription state transition rules.
- Idempotent billing-event inbox model/service.

Not Configured / Missing:
- Stripe is implemented; live credentials and runtime webhook delivery are still environment concerns.
- Fake billing provider is in-memory and test-oriented.
- Workspace checkout, cancel/resume, and plan-change routes exist.
- Stripe signature verification and idempotent billing-event ingestion exist.
- Stripe Checkout session creation exists.
- No invoice API/state workflow.

### Email

Missing:
- Resend and no-op email providers exist.
- Verification/reset email delivery is integrated with idempotent delivery records.

### Storage

Implemented:
- Storage abstraction interface.
- Local filesystem provider with key validation.
- Upload/download/delete lifecycle.

Not Configured / Not production-ready:
- `get_storage_provider()` resolves local or S3 storage through the provider registry.
- `file_storage_backend` supports `local` and `s3`.
- An S3-compatible adapter with multipart uploads is implemented.

### Authentication

Implemented:
- Email/password registration and login.
- Argon2 password hashing.
- Short-lived JWT access token.
- Next.js same-origin BFF stores the access token in an HttpOnly cookie.

Missing:
- Persistent refresh/session mechanism.
- Session rotation/revocation model.
- Password reset.
- Email verification.
- OAuth Google/GitHub with one-time persistent state.
- TOTP 2FA with recovery codes.
- API token subsystem.

Known Limitation:
- Browser session persistence is currently based on a single access-token cookie with a 30-minute configured maximum age; there is no refresh flow.

### Workspace / tenancy

Implemented:
- Workspace CRUD.
- Membership listing.
- Role changes and removal.
- Invitations create/list/revoke/accept.
- Ownership transfer.
- Owner-role database invariant.
- Project/workspace ownership filtering exists in services.

Missing:
- Workspace suspend/reactivate HTTP lifecycle.
- Notifications and notification preferences.

### Jobs

Implemented:
- Durable PostgreSQL-backed job state.
- Idempotent enqueue.
- Claim/heartbeat/complete/fail/cancel.
- Automatic retry decision/backoff.
- Stale-worker reclamation.

Missing:
- UI-visible retry endpoint.

### Research / evidence / knowledge

Implemented:
- Literature routes and Semantic Scholar adapter.
- Screening.
- RAG retrieval.
- Knowledge graph generation/query/node/neighbors/summary.
- Research plan generation/version/coverage/validation.
- Report and manuscript version persistence.
- Humanization and translation preservation logic.

Missing / Partial:
- Claim-centric evidence matrix API is exposed.
- Knowledge graph JSON export endpoint exists.
- Research-plan edit/save/restore endpoints exist.
- Manuscript autosave/edit/restore contract exists.

## M38 frontend status

The design archive contains 21 product pages plus a loading screen. The current Next.js app contains only these actual page routes:
- / (landing)
- /login
- /register
- /dashboard
- /projects
- /projects/[projectId]
- /reports/[reportId]
- /settings/team

The frontend route surface has been expanded across the product areas in the design contract; remaining verification is runtime/typecheck/build evidence.

Current frontend stack:
- Next.js 16
- React 19
- TanStack Query
- React Hook Form
- Zod
- Vitest
- Playwright

The current frontend already uses a same-origin backend BFF, but the application shell still stores workspace selection in localStorage. This is workspace context, not a long-lived authentication credential.

## Backend / platform baseline

Implemented:
- FastAPI route layer with health, auth, research, files, jobs, collaboration, literature, RAG, knowledge graph, reports, workspaces, etc.
- Rate limiting middleware and route-level upload/enqueue/login limits.
- Structured request ID/audit logging primitives.
- Dockerfile and docker-compose files.
- CI workflow containing ruff, mypy, backend tests, a smoke script, frontend unit tests, and API image build.

Known Limitations:
- CI now includes frontend E2E plus repository migration checks; runtime migration/production smoke evidence remains deployment work.
- The health/readiness implementation checks application/DB/job-table availability but does not provide evidence of an independently healthy worker fleet.
- Root README.md and Makefile now document setup and verification commands.

## Migration graph

Static migration inspection found:
- Main chain reaches revision `0032`.
- `14b3d4303f3f_add_report_soft_delete.py` declares `down_revision = "0001_initial_schema"`.

A merge revision `0042` now joins the legacy report soft-delete branch into the implementation chain.

Conclusion: the repository now contains an explicit merge revision; runtime `alembic heads`/upgrade is still a deployment verification step.

## Production-critical gaps found

1. M39 additional real provider registrations — Open (architecture implemented).
2. Real billing provider adapter — Missing.
3. Billing webhook verification/route — Missing.
4. Real email provider/workflows — Missing.
5. Production object storage — Missing.
6. Refresh/session persistence — Missing.
7. Password reset/email verification — Missing.
8. Notification subsystem — Missing.
9. Workspace suspension/reactivation — Missing.
10. Unified authoritative billable metering — Partial.
11. File storage quota accounting — Partial.
12. Claim-centric evidence API — Partial.
13. Research-plan mutation/version restore — Missing/Partial.
14. Manuscript autosave/mutation/conflict workflow — Missing/Partial.
15. Job retry endpoint — Missing.
16. Frontend 21-page production implementation — Missing/Partial.
17. Frontend production CI gates — Partial.
18. Alembic migration graph — Known Limitation / blocker.

## F00 conclusion

F00 establishes the repository baseline. It does not certify M01-M39 as GREEN and does not certify M40 as production-ready.

Next implementation gate: F01 — M39 Provider/Usage Architecture.
