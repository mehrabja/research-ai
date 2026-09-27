# Research-AI — F00 Dependency Matrix

Date: 2026-09-27

| Phase | Depends on | Primary blocker(s) found now | F00 result |
|---|---|---|---|
| F00 | Repository + design archive | None | Baseline recorded |
| F01 Provider/Usage Architecture | F00 | Provider registry/resolver absent; usage split incomplete | Ready to implement |
| F02 Authentication | F01 only for shared policy conventions | No session/refresh, reset, verification | Blocked by current missing contracts |
| F03 Workspace/RBAC/Notifications | F02 for durable identity | Notifications and suspend/reactivate missing | Dependent |
| F04 Storage/File Intelligence | F01/F03 | Local-only provider; 20 MiB vs 500 MB mismatch | Dependent |
| F05 Search/Discovery | F01 + workspace context | Global search/filter/provenance gaps | Dependent |
| F06 Evidence/Knowledge | F05 + existing RAG | Independent claim matrix/export gaps | Dependent |
| F07 Research Planning | F06 | Plan mutation/restore missing | Dependent |
| F08 Manuscript/AI Studio | F01 + F06 + F07 | Autosave/conflict contract missing | Dependent |
| F09 Humanization/Translation | F01 + F08 | Provider resolver not unified | Dependent |
| F10 Jobs/Collaboration | F03 + F08 | Retry endpoint missing | Dependent |
| F11 Billing/Email | F01 + F03 | Real provider, webhook, email all absent | Major blocker |
| F12 Settings/Security/Audit | F02/F03/F11 | 2FA/API tokens/notification settings missing | Dependent |
| F13 Frontend Production Port | F02-F12 contracts | Current UI is only partial; design archive is static | Major dependent work |
| F14 Frontend Integration Hardening | F13 | Real API state handling not complete | Dependent |
| F15 Security/Reliability/Observability | F01-F14 | Provider/webhook/storage/session gaps | Cannot close yet |
| F16 CI/CD/Deployment/Backup | F15 + database state | CI gaps and static migration multi-head | Blocked |
| F17 Production Smoke | F02-F16 | External services not configured | Blocked |
| F18 Chaos/Recovery | F17 | No staging/live integration evidence yet | Blocked |
| F19 Final Audit | F17/F18 | All prior gates | Not reachable |

## Critical dependency chain

F00
→ F01 Provider/Usage
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
