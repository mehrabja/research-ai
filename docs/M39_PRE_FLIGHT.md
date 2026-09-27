# M39 Pre-Flight

## Baseline

- Repository: `mehrabja/research-ai`
- Base commit: `106ca1fd2b5b1b86e4e9521ffa9c33f3d8ddfa91`
- Working branch: `m39-f01-only`
- The supplied 21-page frontend prototype is the UI source of truth. Its README states that it is a static visual prototype and that real backend/API calls are not wired.

## Verified starting capabilities

Email/password authentication; workspace CRUD and membership; projects/reports; sources and retrieval/RAG; literature analysis/screening; knowledge graph generation/query; research plan generation/version/validation; manuscript versioning/validation; humanization/translation pipelines; collaboration/comments/reviews/branches; durable PostgreSQL jobs; project files and intelligence; workspace usage events and plan entitlements; structured errors, request IDs, CORS/trusted-host/rate limiting; provider protocols for generation, embeddings, translation and source search; billing domain/service with a deterministic fake provider.

## Gaps recorded for later phases

Identity: social login, email verification, password reset, persistent refresh/session, 2FA, API tokens.

Platform: global search, notifications, notification preferences, claim-centric evidence contract, graph export, folders, production object storage, retry-failed-job HTTP contract, complete audit/export UI.

SaaS: real checkout, payment provider, authenticated webhook handling, invoices, real email delivery.

Frontend: production implementation of the supplied 21-page design and complete typed API wiring.

## F01 focus

This branch implements only M39 F00/F01:
- preflight/roadmap documentation
- configuration-driven provider chains
- provider registry and capability resolution
- retryable provider fallback policy
- provider operation usage recording using the existing append-only usage tables

No credentials are committed. No provider is reported as configured merely because it is registered in code.

## Important mismatches

- Frontend prototype states a 500 MB per-file policy; current backend configuration is 20 MB.
- Frontend role labels include Editor/Reviewer while backend membership roles are owner/admin/member/viewer.
- Existing concrete provider factories were vendor-specific.
- Usage is split between legacy `usage_logs` and M37 workspace-scoped `usage_events`; F01 records their roles explicitly rather than deleting historical data.

## F01 gate

F01 is not declared GREEN by this branch alone. Tests and runtime/provider verification are intentionally deferred per the execution instruction. The code is the implementation slice; later verification must establish GREEN.
