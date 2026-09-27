# Research-AI — F00 Dependency Matrix

Date: 2026-09-27

| Phase | Depends on | Primary blocker(s) found now | F00 result |
|---|---|---|---|
| F00 | Repository + design archive | None | Baseline recorded |
| F01 Provider/Usage Architecture | F00 | Provider registry/resolver absent; usage split incomplete | Ready to implement / implementation in progress |
| F02 Authentication | F01 + F20 email/OAuth activation when enabled | No session/refresh, reset, verification | Dependent |
| F03 Workspace/RBAC/Notifications | F02 | Notifications and suspend/reactivate missing | Dependent |
| F04 Storage/File Intelligence | F01/F03 + F20 storage provider | Local-only provider; 20 MiB vs 500 MB mismatch | Dependent |
| F05 Search/Discovery | F01 + workspace context + F20 discovery providers as needed | Global search/filter/provenance gaps | Dependent |
| F06 Evidence/Knowledge | F05 + existing RAG | Independent claim matrix/export gaps | Dependent |
| F07 Research Planning | F06 | Plan mutation/restore missing | Dependent |
| F08 Manuscript/AI Studio | F01 + F06 + F07 | Autosave/conflict contract missing | Dependent |
| F09 Humanization/Translation | F01 + F08 + F20 detector | Real detector provider missing | Dependent |
| F10 Jobs/Collaboration | F03 + F08 | Retry endpoint missing | Dependent |
| F11 Billing/Email | F01 + F03 + F20 email/billing | Real provider, webhook, email all absent | Major blocker |
| F12 Settings/Security/Audit | F02/F03/F11 | 2FA/API tokens/notification settings missing | Dependent |
| F13 Frontend Production Port | F02-F12 contracts | Current UI is only partial; design archive is static | Major dependent work |
| F14 Frontend Integration Hardening | F13 | Real API state handling not complete | Dependent |
| F15 Security/Reliability/Observability | F01-F14 + F20 | Provider/webhook/storage/session gaps | Cannot close yet |
| F16 CI/CD/Deployment/Backup | F15 + database state | CI gaps and static migration multi-head | Blocked |
| F17 Production Smoke | F02-F16 + F20 credentials | External services not configured | Blocked |
| F18 Chaos/Recovery | F17 | No staging/live integration evidence yet | Blocked |
| F19 Final Audit | F17/F18 | All prior gates | Not reachable |

## Cross-cutting operational phase

### F20 — External Service Provisioning & Provider Activation

F20 is not a replacement for feature phases. It is the external-service gate that feeds them.

Execution order:

```
F01 provider architecture
        |
        v
F20 external credentials + provider adapters
        |
        +--> F02 auth email/OAuth (when enabled)
        +--> F04 production object storage
        +--> F05 research discovery scale/diversity
        +--> F09 real AI detection
        +--> F11 email + billing
        +--> F15 production observability
        +--> F17 production smoke
```

F20 must produce:
- OpenRouter generation/embedding activation.
- Semantic Scholar production credentials.
- One production object-storage adapter (R2 or S3).
- One transactional email provider.
- One real AI-detection provider.
- One billing provider plus verified webhooks.
- OAuth credentials only when social login is enabled.
- Optional telemetry/abuse-control services only when approved.

## Critical feature gaps from the M38 design

The following are now explicitly operational work, not optional frontend decoration:

```
Auth:
session/refresh
password reset
email verification
optional OAuth

Workspace:
suspend/reactivate
notifications/preferences

Research:
global search
richer academic discovery
claim-centric evidence
graph export
plan mutation/restore
manuscript autosave/conflict

AI:
OpenRouter provider
real detection provider

Operations:
job retry
user-facing activity
production object storage
storage metering
folders

SaaS:
real email
real billing/webhooks
2FA
API tokens

Release:
full frontend route coverage
frontend build/typecheck/e2e
migration verification
external-service smoke tests
```

## Critical dependency chain

F00
→ F01 Provider/Usage
→ F20 External Service Activation
→ F02 Auth
→ F03 Workspace/RBAC
→ F04 Storage
→ F05 Search
→ F06 Evidence
→ F07 Plan
→ F08 Manuscript
→ F09 AI transformations
→ F10 Jobs/Collaboration
→ F11 Billing/Email
→ F12 Security/Settings
→ F13 Frontend
→ F14 Integration hardening
→ F15 Security/Observability
→ F16 Deployment/Backup
→ F17 Smoke
→ F18 Chaos
→ F19 Final Audit

F20 can run in parallel only where its prerequisites are independently satisfied, but no production
gate can be closed without the specific external service dependencies required by that gate.
