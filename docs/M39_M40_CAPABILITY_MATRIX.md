# M39/M40 Capability Matrix — Current Branch Audit

Branch audited: `m39-production-capabilities`

Status vocabulary:
- **Implemented** — code/route/model exists in the current branch.
- **Partial** — implemented but integration, authorization, tests, provider configuration, or production hardening remains.
- **Not configured** — production adapter exists but credentials/config are intentionally absent.
- **Missing** — no implementation found in the current branch.

| Capability | Current state | Remaining work | Phase |
|---|---|---|---|
| Email/password | Implemented / Partial | verification policy + full integration tests | F02 |
| Persistent refresh/session | Implemented / Partial | replay/family hardening + tests | F02 |
| Email verification | Implemented / Partial | production email delivery verification | F02/F11 |
| Password reset | Implemented / Partial | delivery/rate-limit tests | F02/F11 |
| Google OAuth | Implemented / Not configured | credentials + integration verification | F02 |
| GitHub OAuth | Implemented / Not configured | credentials + integration verification | F02 |
| Global search | Implemented / Partial | full ranking/provenance test coverage | F05 |
| Notifications | Implemented / Partial | event producers + delivery preferences | F03/F11 |
| Workspace lifecycle | Implemented / Partial | full suspension/reactivation policy verification | F03 |
| Invitations | Implemented / Partial | email delivery + lifecycle tests | F03/F11 |
| RBAC / role mapping | Implemented / Partial | complete action matrix + isolation tests | F03 |
| Research discovery | Implemented / Partial | advanced filters/provider outage/pagination tests | F05 |
| Literature analysis | Implemented | integration verification | F05 |
| Screening | Implemented | integration/audit verification | F05 |
| RAG / retrieval | Implemented / Partial | provider metering + provenance integration | F06/F08 |
| Claim-centric evidence matrix | Implemented / Partial | provenance/manuscript binding tests | F06 |
| Knowledge graph | Implemented | graph consistency verification | F06 |
| Knowledge graph export | Implemented | authorization/export integration tests | F06 |
| Files | Implemented / Partial | storage quota + production adapter verification | F04 |
| File folders | Implemented | hierarchy/isolation tests | F04 |
| File size | Implemented / Partial | document-fetch vs upload limits explicitly documented | F04 |
| S3/object storage | Implemented / Not configured | production credentials + signed-access verification | F04/F15 |
| File intelligence | Implemented / Partial | failure/retry/provider integration tests | F04 |
| Research-plan generate | Implemented | end-to-end verification | F07 |
| Research-plan save/edit | Implemented | immutable-version/concurrency tests | F07 |
| Manuscript architecture | Implemented | end-to-end verification | F08 |
| Manuscript autosave | Implemented / Partial | concurrency/conflict test coverage | F08 |
| Manuscript snapshots | Implemented / Partial | version-content verification | F08 |
| AI Studio | Partial | complete operation/context/policy contract verification | F08 |
| Grounded generation | Partial | connect every generation path to evidence + AI ledger | F08 |
| Citation/evidence binding | Partial | end-to-end provenance verification | F08 |
| Humanization | Implemented / Partial | version/job/usage integration verification | F09 |
| Translation | Implemented / Partial | provider routing + usage + preservation verification | F09 |
| Job retry/cancel/reclaim | Implemented / Partial | UI contract + end-to-end tests | F10 |
| Collaboration/review | Implemented / Partial | complete authorization/audit test suite | F10 |
| Usage | Implemented / Partial | eliminate legacy-vs-product ambiguity and double counting | F01/F11 |
| Provider registry | Implemented / Partial | multi-provider fallback execution | F01 |
| Provider operation ledger | Implemented / Partial | wire into every AI/search/translation call | F01 |
| Real billing checkout | Implemented / Not configured | sandbox credentials + live verification | F11 |
| Billing webhook | Implemented / Partial | signature/replay/idempotency integration verification | F11 |
| Invoices | Implemented | provider reconciliation verification | F11 |
| Email provider | Implemented / Not configured | SMTP/provider credentials + delivery verification | F11 |
| 2FA | Implemented / Partial | complete auth challenge/recovery integration tests | F12 |
| Sessions UI API | Implemented / Partial | complete revocation/refresh tests | F12 |
| API tokens | Implemented / Partial | scope enforcement + auth integration | F12 |
| Audit UI/API | Partial | complete tenant-scoped audit query contract | F12/F15 |
| Dashboard aggregate | Implemented / Partial | frontend wiring | F13 |
| Production frontend | Missing | port supplied 21-page design | F13 |
| Frontend typed API | Partial | replace remaining demo/static behavior | F13/F14 |
| Frontend loading/error/retry states | Partial | all 21 pages | F14 |
| Security hardening | Partial | full M40 security pass | F15 |
| Observability | Partial | full provider/job/request trace coverage | F15 |
| Backup/restore | Partial | tested restore procedure | F16 |
| CI/CD | Partial | current branch full CI verification | F16 |
| Production smoke | Missing | full scenario | F17 |
| Chaos/recovery | Missing | failure suite | F18 |
| Final launch audit | Missing | M40 GREEN gates | F19 |

## Current explicit blockers

1. Alembic must have a single verified head after the `0043` merge.
2. Provider fallback must execute across retryable provider failures, not merely list candidates.
3. Every actual AI pipeline needs to write the AI operation/usage records consistently.
4. Production environment must not allow insecure cookie/local-storage defaults.
5. The supplied 21-page frontend is not yet the production UI.
