# Research-AI Capability Matrix — F00

Date: 2026-09-27
Baseline commit: 106ca1fd2b5b1b86e4e9521ffa9c33f3d8ddfa91

| Capability | Backend | Provider/abstraction | Persistence | Frontend/design | F00 status |
|---|---|---|---|---|---|
| Email/password auth | Yes | JWT primitive | User | Login/Signup | Implemented / not runtime-verified |
| Refresh/session | No | No session provider | No session model | Loading/auth bootstrap | Missing |
| Email verification | No | No email provider | No verification model | Signup flow | Missing |
| Password reset | No | No email provider | No reset model | Login flow | Missing |
| Google/GitHub OAuth | No | No OAuth adapter | No identity linkage | Login design includes both | Missing |
| Workspace CRUD | Yes | N/A | Workspace | Workspace | Implemented |
| Membership/RBAC | Yes | N/A | Membership | Team/Workspace | Implemented |
| Invitations | Yes | N/A | Invitation/token hash | Team | Implemented |
| Ownership transfer | Yes | N/A | Membership/workspace | Settings/Team | Implemented |
| Suspension/reactivation | Partial | N/A | Workspace status exists | Settings | Missing API lifecycle |
| Notifications | No | No email/in-app layer | No notification model | Bell/settings | Missing |
| Projects | Yes | N/A | Project | Dashboard/Workspace | Implemented |
| Reports/versioning | Yes | N/A | Report/versions/events | Manuscript/Reports | Implemented |
| Literature | Yes | Semantic Scholar adapter | Literature models | Research/Literature | Partial |
| Search discovery | Yes | Semantic Scholar | Sources | Research | Partial |
| Evidence/RAG | Yes | Retrieval stack | Retrieval models | Evidence | Partial |
| Claim-centric evidence matrix | Partial | N/A | no independent claim contract found | Evidence design | Partial |
| Knowledge graph | Yes | Internal services | Graph models | Knowledge | Implemented |
| Graph export | No | N/A | Existing graph data | Knowledge | Missing |
| Files | Yes | Local storage abstraction | ProjectFile | Files | Implemented |
| Production object storage | No | Local only | Storage metadata | Files | Missing |
| File folders | No | N/A | No folder model | Files | Missing |
| File max size contract | Yes | Configurable backend, currently 20 MiB default | ProjectFile | Design says 500 MB | Mismatch |
| File intelligence | Yes | Extractors/intelligence | File events/meta | Files | Partial |
| Research plan | Yes | Generation/planning services | Versioned plan | Plan | Partial |
| Plan edit/save/restore | No | N/A | No mutation contract | Plan | Missing |
| Manuscript | Yes | Generation/version services | Versioned manuscript | Manuscript | Partial |
| Manuscript autosave/conflict | No explicit contract | N/A | No autosave API found | Manuscript | Missing/Partial |
| AI Studio generation | Yes | OpenAI generation adapter | Report versions/usage logs | Generate | Partial |
| Humanization | Yes | Injectable provider | Humanization runs/rewrites | Humanize | Partial |
| Translation | Yes | OpenAI adapter | Translation runs/versions | Translate | Partial |
| Jobs | Yes | Durable DB queue | Job model | Jobs | Implemented |
| Job retry UI/API | No UI retry endpoint | Retry policy exists | Job state | Jobs | Missing |
| Collaboration/reviews | Yes | Internal | Review/comment/version models | Collaboration | Implemented/Partial |
| Usage | Yes | Workspace usage events + legacy usage logs | UsageEvent/UsageLog | Usage & Billing | Partial |
| Billing model | Yes | Fake/none only | Subscription/BillingEvent | Usage & Billing | Partial |
| Real checkout | No | No real provider | No checkout model | Billing | Missing |
| Billing webhook | No | No signature adapter | Billing event inbox exists | Billing | Missing |
| Email | No | No provider | No delivery record | Settings/notifications | Missing |
| Audit | Yes | Structured audit logger | Log-based | Settings/Audit | Partial |
| API tokens | No | N/A | No token model | Settings | Missing |
| 2FA | No | N/A | No 2FA model | Settings | Missing |
| Health | Yes | DB/live checks | N/A | Loading/system | Implemented / not runtime-verified |
| CI | Yes | GitHub Actions | N/A | N/A | Partial |
