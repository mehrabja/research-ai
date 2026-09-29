# Research-AI Capability Matrix — F00

Date: 2026-09-27
Baseline commit: 106ca1fd2b5b1b86e4e9521ffa9c33f3d8ddfa91

| Capability | Backend | Provider/abstraction | Persistence | Frontend/design | F00 status |
|---|---|---|---|---|---|
| Email/password auth | Yes | JWT primitive | User | Login/Signup | Implemented / not runtime-verified |
| Refresh/session | Yes | Persistent hashed refresh sessions | AuthSession | BFF rotation | Implemented (code) |
| Email verification | Yes | Resend/none provider path | One-time token + User timestamp | Verification UI | Implemented (code) |
| Password reset | Yes | Resend/none provider path | One-time reset token | Reset UI | Implemented (code) |
| Google/GitHub OAuth | Yes | Provider REST exchange | OAuthAccount/OAuthState | Login callbacks | Implemented (code) |
| Workspace CRUD | Yes | N/A | Workspace | Workspace | Implemented |
| Membership/RBAC | Yes | N/A | Membership | Team/Workspace | Implemented |
| Invitations | Yes | N/A | Invitation/token hash | Team | Implemented |
| Ownership transfer | Yes | N/A | Membership/workspace | Settings/Team | Implemented |
| Suspension/reactivation | Yes | N/A | Workspace status | Workspace lifecycle routes | Implemented (code) |
| Notifications | Yes | In-app + Resend delivery | Notification/Preference | Settings/inbox | Implemented (code) |
| Projects | Yes | N/A | Project | Dashboard/Workspace | Implemented |
| Reports/versioning | Yes | N/A | Report/versions/events | Manuscript/Reports | Implemented |
| Literature | Yes | Semantic Scholar adapter | Literature models | Research/Literature | Partial |
| Search discovery | Yes | Semantic Scholar | Sources | Research | Partial |
| Evidence/RAG | Yes | Retrieval stack | Retrieval models | Evidence | Partial |
| Claim-centric evidence matrix | Yes | Internal evidence/citation graph | Claims/Evidence/Citations | Evidence API surface | Implemented (code) |
| Knowledge graph | Yes | Internal services | Graph models | Knowledge | Implemented |
| Graph export | Yes | Internal | Existing graph data | Knowledge export | Implemented (code) |
| Files | Yes | Local storage abstraction | ProjectFile | Files | Implemented |
| Production object storage | Yes | Local/S3 registry | Storage metadata | Files | Implemented (code) |
| File folders | Yes | N/A | ProjectFolder + File.folder_id | Files | Implemented (code) |
| File max size contract | Yes | Streaming upload enforcement up to 500 MB | ProjectFile | Design says 500 MB | Implemented |
| File intelligence | Yes | Extractors/intelligence | File events/meta | Files | Partial |
| Research plan | Yes | Generation/planning services | Versioned plan | Plan | Partial |
| Plan edit/save/restore | Yes | Internal planner | Versioned plan graph | Plan UI/API | Implemented (code) |
| Manuscript | Yes | Generation/version services | Versioned manuscript | Manuscript | Partial |
| Manuscript autosave/conflict | Yes | Internal editor | Draft buffer + immutable versions | Manuscript UI/API | Implemented (code) |
| AI Studio generation | Yes | OpenAI generation adapter | Report versions/usage logs | Generate | Partial |
| Humanization | Yes | Injectable provider | Humanization runs/rewrites | Humanize | Partial |
| Translation | Yes | OpenAI adapter | Translation runs/versions | Translate | Partial |
| Jobs | Yes | Durable DB queue | Job model | Jobs | Implemented |
| Job retry UI/API | Yes | Durable queue | Job state | Jobs retry endpoint | Implemented (code) |
| Collaboration/reviews | Yes | Internal | Review/comment/version models | Collaboration | Implemented/Partial |
| Usage | Yes | Workspace usage events for AI/search plus legacy compatibility adapters | UsageEvent/UsageLog | Usage & Billing | Implemented in code |
| Billing model | Yes | Fake/none only | Subscription/BillingEvent | Usage & Billing | Partial |
| Real checkout | Yes | Stripe REST | Subscription/BillingEvent | Billing API | Implemented (code) |
| Billing webhook | Yes | Stripe signature verification | BillingEvent | Webhook route | Implemented (code) |
| Email | Yes | Resend adapter | EmailDelivery | Auth workflow delivery | Implemented (code) |
| Audit | Yes | Structured audit logger + safe user activity projection | Log-based + durable security records | Settings/Security activity | Implemented (code) |
| API tokens | Yes | X-API-Key auth | APIToken | Security UI | Implemented (code) |
| 2FA | Yes | TOTP | User MFA fields | Security UI | Implemented (code) |
| Health | Yes | DB/live checks | N/A | Loading/system | Implemented / not runtime-verified |
| CI | Yes | GitHub Actions | N/A | N/A | Partial |
