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

**RED for M40 entry.**

### Provider interfaces

Implemented:
- Generation provider protocol and typed error contract.
- Embedding provider protocol and typed error contract.
- Translation provider protocol and typed error contract.
- Detection provider protocol and typed error contract.
- Source/literature provider protocol and typed error contract.
- Billing provider protocol.

Not verified/configured:
- No project-wide provider registry or resolver was found.
- Generation/embedding factories directly construct OpenAI providers.
- Translation factory only accepts OpenAI.
- Detection factory only accepts the heuristic provider.
- Billing domain only declares `none` and `fake`.

### Resilience

Implemented:
- Provider-local retry/backoff exists for OpenAI generation and embeddings.
- Semantic Scholar adapter has retry/backoff and typed failure mapping.
- Durable job retry/reclaim primitives exist.

Known Limitation:
- No common cross-capability fallback policy/resolver is present.

### Usage

Implemented:
- M37 `usage_events` model and idempotent workspace-scoped recorder.
- Metrics include: reports_created, jobs_enqueued, files_uploaded, storage_bytes, ai_generation_units, search_requests.
- Legacy provider-aware `usage_logs` remain in generation/embedding/translation paths.

Known Limitations:
- Storage aggregation is explicitly marked as not wired in the workspace usage route.
- A unified authoritative distinction between provider usage, product usage, and billable usage is not yet implemented.

### Billing

Implemented:
- Provider protocol.
- Subscription model.
- Subscription state transition rules.
- Idempotent billing-event inbox model/service.

Not Configured / Missing:
- Only `none` and `fake` providers.
- Fake billing provider is in-memory and test-oriented.
- No billing HTTP route.
- No authenticated webhook route.
- No real checkout/session creation flow.
- No invoice API/state workflow.

### Email

Missing:
- No email provider integration was found.
- No verification/reset/invitation transactional email provider or delivery job layer was found.

### Storage

Implemented:
- Storage abstraction interface.
- Local filesystem provider with key validation.
- Upload/download/delete lifecycle.

Not Configured / Not production-ready:
- `get_storage_provider()` always returns `LocalStorageProvider`.
- Configuration only permits `file_storage_backend=local`.
- No production object-storage adapter was found.

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
- OAuth Google/GitHub.
- 2FA.
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
- Claim-centric evidence contract is not exposed as an independent API contract.
- Knowledge graph export endpoint is absent.
- Research-plan edit/save/restore endpoints are absent.
- Manuscript autosave/edit/restore contract is absent.

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

Therefore the current frontend is **partial** against the 21-page product contract.

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
- CI does not currently run the frontend production build, frontend typecheck, frontend E2E suite, or migration upgrade/downgrade verification.
- The health/readiness implementation checks application/DB/job-table availability but does not provide evidence of an independently healthy worker fleet.
- Root README.md and Makefile are empty.

## Migration graph

Static migration inspection found:
- Main chain reaches revision `0032`.
- `14b3d4303f3f_add_report_soft_delete.py` declares `down_revision = "0001_initial_schema"`.

No later join migration was found in the repository tree.

Conclusion: the Alembic graph is **multi-head by static inspection** unless an external/runtime configuration joins the branches. Runtime `alembic heads` was not executed in F00.

## Production-critical gaps found

1. M39 provider registry/resolver/fallback policy — Missing.
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
