# Research-AI — F00 Gap Matrix

Date: 2026-09-27
Baseline commit: 106ca1fd2b5b1b86e4e9521ffa9c33f3d8ddfa91

| ID | Gap | Severity | Evidence | Target phase | Status |
|---|---|---|---|---|---|
| G-01 | Global provider registry/resolver missing | P0 | centralized `app/providers/registry.py`; generation/embedding/translation/detection/source factories now resolve through it | F01 | Implemented |
| G-02 | Universal fallback policy missing | P0 | `PROVIDER_FALLBACKS` routing plus `FallbackProvider` transient-failure chain | F01 | Implemented (additional real providers still required) |
| G-03 | Unified provider error contract missing | P1 | routing is centralized; capability-specific typed errors remain by design | F01 | Partial |
| G-04 | Real provider configuration model missing | P0 | config has per-provider fields and now external-service placeholders, but not all adapters are activated | F01/F20 | Partial |
| G-05 | Persistent refresh/session mechanism missing | P0 | only access JWT + BFF cookie | F02 | Missing |
| G-06 | Password reset missing | P0 | no route/model | F02 | Missing |
| G-07 | Email verification missing | P0 | User model has no verification state | F02 | Missing |
| G-08 | OAuth missing | P2 | no OAuth routes/models | F02 | Missing |
| G-09 | 2FA missing | P1 | no 2FA model/routes | F12 | Missing |
| G-10 | API token subsystem missing | P1 | no token model/routes | F12 | Missing |
| G-11 | Notifications missing | P1 | no notification model/routes | F03/F11 | Missing |
| G-12 | Workspace suspend/reactivate API missing | P1 | status exists, lifecycle route absent | F03 | Missing |
| G-13 | Production object storage missing | P0 | LocalStorageProvider is sole implementation | F04/F20 | Missing |
| G-14 | File size mismatch | P0 | backend default 20 MiB; design says 500 MB | F04/F13 | Open |
| G-15 | File folders missing | P1 | no folder model/route | F04 | Missing |
| G-16 | Storage quota accounting incomplete | P0 | workspace usage route comments aggregation is not wired | F04/F11 | Partial |
| G-17 | Global search missing | P1 | no general search route | F05 | Missing |
| G-18 | Advanced discovery filters incomplete | P1 | current literature/source contracts are narrower than design | F05 | Partial |
| G-19 | Claim-centric evidence API incomplete | P0 | RAG retrieval exists; independent claim matrix contract not found | F06 | Partial |
| G-20 | Knowledge graph export missing | P1 | generate/query/node/neighbors/summary only | F06 | Missing |
| G-21 | Research plan mutation/restore missing | P1 | generate/get/versions/coverage/validate only | F07 | Missing |
| G-22 | Manuscript autosave/conflict API missing | P1 | get/generate/version/validate present, no autosave contract found | F08 | Missing |
| G-23 | Job retry endpoint missing | P1 | auto-retry exists; API exposes enqueue/get/list/cancel | F10 | Missing |
| G-24 | Real billing provider missing | P0 | billing provider union is none/fake | F11/F20 | Missing |
| G-25 | Billing webhook verification missing | P0 | no webhook route or signature adapter | F11/F20 | Missing |
| G-26 | Email provider/workflows missing | P0 | no email integration | F11/F20 | Missing |
| G-27 | Unified billable metering incomplete | P0 | UsageEvent exists but provider operations still write legacy UsageLog | F11/F15 | Partial |
| G-28 | Frontend 21-page production port incomplete | P0 | only 8 actual Next page routes | F13 | Partial |
| G-29 | Frontend production CI gates incomplete | P1 | CI lacks web build/typecheck/e2e | F16 | Partial |
| G-30 | Migration graph has static multi-head condition | P0 | 14b3 migration revises 0001 while main chain reaches 0032 | F16 | Blocker |
| G-31 | Root product/developer docs absent | P1 | root README and Makefile are empty | F16/F19 | Missing |
| G-32 | Real OpenRouter provider adapter not activated | P0 | provider registry is present, but no OpenRouter adapter is registered | F20 | Missing |
| G-33 | Production AI detection provider missing | P1 | detection capability currently resolves to heuristic provider only | F09/F20 | Missing |
