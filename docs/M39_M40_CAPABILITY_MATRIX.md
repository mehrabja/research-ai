# M39/M40 Capability Matrix

Status meanings: Present = backend capability existed at baseline; Partial = contract exists but integration/production hardening is incomplete; Missing = no complete contract at baseline.

| Capability | Baseline | Target phase | GREEN evidence |
|---|---|---|---|
| Email/password auth | Present | F02 | register/login integration tests |
| Persistent refresh/session | Missing | F02 | rotation/revoke/session tests |
| Email verification | Missing | F02/F11 | token lifecycle + delivery test |
| Password reset | Missing | F02/F11 | single-use reset + session invalidation |
| Google OAuth | Missing | F02 | callback/state/account-link tests with configured provider |
| GitHub OAuth | Missing | F02 | callback/state/account-link tests with configured provider |
| Global search | Missing | F05 | tenant-scoped search tests |
| Notifications | Missing | F03/F11 | unread/read/preferences tests |
| Workspace lifecycle | Mostly present | F03 | authorization + owner invariant tests |
| Invite lifecycle | Present/Partial | F03/F11 | create/resend/revoke/accept delivery tests |
| Role mapping | Partial | F03 | explicit permission matrix |
| Research discovery | Partial | F05 | provider provenance/pagination/dedup tests |
| Advanced discovery filters | Partial | F05 | filter contract tests |
| Literature analysis | Present | F05 | integration tests |
| Screening | Present | F05 | override/audit tests |
| RAG/retrieval | Present | F06/F08 | retrieval provenance tests |
| Claim-centric evidence | Partial | F06 | claim/evidence CRUD + provenance |
| Knowledge graph | Present | F06 | graph consistency tests |
| Knowledge graph export | Missing | F06 | JSON/CSV authorization tests |
| Files | Present | F04 | upload/download/delete tests |
| File folders | Missing | F04 | hierarchy/isolation tests |
| File size contract | Mismatch (20MB vs UI 500MB) | F04/F13 | one backend source of truth |
| Object storage | Local only | F04/F15 | production adapter contract |
| File intelligence | Present/Partial | F04 | extraction/intelligence lifecycle tests |
| Research-plan generate | Present | F07 | generation tests |
| Research-plan save/edit | Missing/Partial | F07 | immutable version mutation tests |
| Manuscript architecture | Present | F08 | version tests |
| Manuscript autosave | Missing | F08 | optimistic-lock + history tests |
| Manuscript content snapshot | Missing | F08 | version content persistence tests |
| AI Studio operations | Partial | F08 | grounded context contract tests |
| Citation/evidence binding | Partial | F08 | provenance chain tests |
| Humanization | Present/Partial | F09 | preservation/version/job tests |
| Translation | Present/Partial | F09 | preservation/version/idempotency tests |
| Jobs retry | Missing UI contract | F10 | failed→queued retry tests |
| Collaboration/review | Present/Partial | F10 | auth/review lifecycle tests |
| Usage events | Present/Partial | F01/F11 | idempotent usage ledger |
| Provider registry/resolver | Partial → implementing | F01 | routing/fallback/error tests |
| Billing domain | Present/Partial | F11 | normalized lifecycle tests |
| Real checkout | Missing | F11 | sandbox checkout integration |
| Billing webhook | Missing | F11 | signature/replay/idempotency tests |
| Invoices | Missing | F11 | invoice API tests |
| Email provider | Missing | F11 | sandbox delivery + retry tests |
| 2FA | Missing | F12 | enrollment/challenge/recovery tests |
| API tokens | Missing | F12 | hash/scope/revoke tests |
| Audit/export UI | Partial | F12/F15 | queryable tenant-scoped audit tests |
| Production frontend | Missing | F13 | all 21 pages typed/API wired |
| UI error/loading/retry states | Missing/Partial | F14 | page-state tests |
| Security hardening | Partial | F15 | security test suite |
| Observability | Partial | F15 | request/job/provider traceability |
| Backup/restore | Partial | F16 | restore verification |
| CI/CD | Partial | F16 | required checks green |
| Production smoke | Missing | F17 | full scenario pass |
| Chaos/recovery | Missing | F18 | failure/recovery suite |
| Launch audit | Missing | F19 | no unexplained RED gates |
