# M39 Pre-Flight

## Baseline
- Repository: mehrabja/research-ai
- Base commit: 106ca1fd2b5b1b86e4e9521ffa9c33f3d8ddfa91
- Working branch: m39-production-capabilities
- The supplied 21-page frontend prototype is the UI source of truth; its own README says it is static and not wired to the backend.

## Verified backend capabilities
- Email/password auth
- Workspace CRUD and membership primitives
- Projects/reports
- Sources and retrieval/RAG
- Literature analysis and screening
- Knowledge graph generation/query
- Research plan generation/version/validation
- Manuscript versioning/validation
- Humanization and translation pipelines
- Collaboration/comments/reviews/branches
- Durable PostgreSQL jobs with retry/heartbeat/reclaim
- Project file upload/list/download/delete and intelligence
- Workspace usage events and plan entitlements
- Security middleware, request IDs, structured errors and rate limits
- Provider protocols for generation, embeddings, translation and source search
- Billing domain/service with deterministic fake provider for tests

## Known gaps
Identity: social login, email verification, password reset, refresh/session persistence, 2FA, API tokens.
Platform: global search, notifications, notification preferences, claim-centric evidence contract, graph export, file folders, production object storage, retry-failed-job HTTP contract, full audit/export UI contract.
Provider/usage: registry/resolver/capability policy, fallback policy, unified provider/internal/billable usage semantics, AI operation ledger, consistent error mapping.
SaaS: real checkout, payment subscription provider, authenticated webhooks, invoice model/API, real email provider and delivery lifecycle.
UI integration: replacement frontend implementation, typed API wiring, complete loading/empty/error/forbidden/retry states, dashboard aggregation.

## Important mismatches
- UI prototype says 500 MB per file; backend currently uses a 20 MB document/upload cap.
- UI role labels include Editor/Reviewer; backend membership roles are owner/admin/member/viewer.
- Multiple services instantiate concrete vendors directly.
- Usage is split between workspace-scoped usage_events and legacy user/report-scoped usage_logs.

## Gate
M39 is not GREEN until provider routing, usage attribution, authentication/session contracts, workspace authorization and their tests are implemented and verified. M40 cannot be declared GREEN before this gate.