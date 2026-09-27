# Research-AI — F00 Gap Matrix

Date: 2026-09-27
Baseline commit: 106ca1fd2b5b1b86e4e9521ffa9c33f3d8ddfa91

| ID | Gap | Severity | Evidence | Target phase | Status |
|---|---|---|---|---|---|
| G-01 | Global provider registry/resolver missing | P0 | centralized `app/providers/registry.py`; generation/embedding/translation/detection/source factories now resolve through it | F01 | Implemented |
| G-02 | Universal fallback policy missing | P0 | `PROVIDER_FALLBACKS` routing plus `FallbackProvider` transient-failure chain | F01 | Implemented (additional real providers still required) |
| G-03 | Unified provider error contract missing | P1 | generation, embedding, translation, detection, and source adapters inherit the shared ProviderError/ProviderRetryableError hierarchy | F01/F20 | Implemented |
| G-04 | Real provider configuration model missing | P0 | typed provider configuration and registry-backed adapters now exist for generation, embedding, translation, detection, discovery, billing, email, storage | F01/F20 | Implemented |
| G-05 | Persistent refresh/session mechanism missing | P0 | persistent hashed refresh sessions plus BFF rotation/retry | F02 | Implemented |
| G-06 | Password reset missing | P0 | single-use hashed reset tokens and confirm endpoint | F02 | Implemented |
| G-07 | Email verification missing | P0 | verification timestamp, single-use tokens, resend and delivery integration | F02/F11 | Implemented |
| G-08 | OAuth missing | P2 | Google/GitHub account linkage and authorization-code exchange routes | F12 | Implemented |
| G-09 | 2FA missing | P1 | TOTP enrollment, enable/disable, recovery codes, login enforcement | F12 | Implemented |
| G-10 | API token subsystem missing | P1 | hashed personal API tokens with create/list/revoke and X-API-Key auth | F12 | Implemented |
| G-11 | Notifications missing | P1 | persisted in-app notifications with read/unread APIs and membership event emission | F03/F11 | Implemented |
| G-12 | Workspace suspend/reactivate API missing | P1 | owner-only lifecycle routes and state transitions | F03 | Implemented |
| G-13 | Production object storage missing | P0 | S3-compatible provider with multipart upload and configurable backend | F04/F20 | Implemented |
| G-14 | File size mismatch | P0 | document_max_bytes aligned to 500 MB and generic body buffering bypassed for streaming file uploads | F04/F13 | Implemented |
| G-15 | File folders missing | P1 | folder tree model, CRUD, file placement and move routes | F04 | Implemented |
| G-16 | Storage quota accounting incomplete | P0 | authoritative active-byte aggregation and upload-time quota reservation | F04 | Implemented |
| G-17 | Global search missing | P1 | workspace-scoped project/report/source/file search and frontend surface | F05/F13 | Implemented |
| G-18 | Advanced discovery filters incomplete | P1 | source discovery now supports year ranges, citation ranges, author, venue, publication type, language, OA, and deterministic sorting | F05 | Implemented |
| G-19 | Claim-centric evidence API incomplete | P0 | claim evidence/citation matrix endpoint with provenance-linked rows | F06 | Implemented |
| G-20 | Knowledge graph export missing | P1 | bounded JSON export endpoint | F06 | Implemented |
| G-21 | Research plan mutation/restore missing | P1 | immutable revision save/restore with copied dependency graph | F07 | Implemented |
| G-22 | Manuscript autosave/conflict API missing | P1 | mutable draft buffer, optimistic revision checks, commit/discard endpoints | F08 | Implemented |
| G-23 | Job retry endpoint missing | P1 | manual retry resets terminal job state through the durable queue service | F10 | Implemented |
| G-24 | Real billing provider missing | P0 | Stripe REST adapter, checkout, cancel/resume and plan-change surface | F11/F20 | Implemented |
| G-25 | Billing webhook verification missing | P0 | Stripe signature verification, idempotent billing inbox, subscription reconciliation | F11/F20 | Implemented |
| G-26 | Email provider/workflows missing | P0 | Resend adapter plus idempotent delivery records wired to auth flows | F11/F20 | Implemented |
| G-27 | Unified billable metering incomplete | P0 | authoritative workspace UsageEvent is populated by generation, embedding, translation, source search, global search, and legacy humanization adapters; UsageLog remains compatibility history | F11/F15 | Implemented (legacy compatibility retained) |
| G-28 | Frontend 21-page production port incomplete | P0 | protected route surface now covers dashboard, projects, research, sources, literature, evidence, planning, knowledge graph, manuscript, jobs, files, search, billing, collaboration, review, translation, usage, and settings/security/integrations/notifications | F13 | Implemented in code |
| G-29 | Frontend production CI gates incomplete | P1 | web typecheck/build already gated; Playwright E2E gate added | F16 | Implemented |
| G-30 | Migration graph has static multi-head condition | P0 | explicit merge revision 0042 joins legacy report branch into the production chain | F16 | Implemented |
| G-31 | Root product/developer docs absent | P1 | root README and Makefile now document setup and verification commands | F16/F19 | Implemented |
| G-32 | Real OpenRouter provider adapter not activated | P0 | OpenRouter generation/embedding/translation adapters registered in provider registry | F20 | Implemented |
| G-33 | Production AI detection provider missing | P1 | configurable external HTTP detection adapter registered alongside heuristic fallback | F09/F20 | Implemented |
