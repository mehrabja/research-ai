# Research-AI — Operational Feature & External API Roadmap

Date: 2026-09-29
Branch: phase123-integration

## Purpose

The M38 frontend design contains several product capabilities that are not fully backed by the
current backend or pipeline. Those capabilities must become explicit operational work, not
decorative UI.

Rule:

```
Frontend feature
    -> real backend contract
    -> real persistence/job semantics
    -> real external provider when required
    -> production secret/configuration
    -> tests
```

A feature is not complete merely because a page or button exists.

## Frontend-design features that must be added to operational phases

| Design capability | Current backend state | Operational phase | Required backend work |
|---|---|---|---|
| Persistent sessions / refresh | Access JWT only | F02 | Session/refresh token persistence, rotation, revocation, logout semantics |
| Password reset | Missing | F02 | Reset-token persistence, request/consume endpoints, expiry/replay protection |
| Email verification | Missing | F02 + F11 | Verification state + token flow + transactional email |
| Google/GitHub OAuth | Missing | F02 + F12 | Identity linkage, OAuth callback/state/PKCE policy |
| Workspace suspension/reactivation | Status exists, lifecycle API absent | F03 | Suspend/reactivate endpoints + authorization/audit |
| Notification center/preferences | Missing | F03 + F11 | Notification persistence, read/unread state, preference model, delivery hooks |
| Production object storage | Local-only | F04 | S3-compatible provider, private objects, signed downloads/uploads |
| File folders | Missing | F04 | Folder model, nesting rules, move/list endpoints |
| Storage metering/quota | Aggregation not wired | F04 + F11 | Authoritative byte accounting and quota enforcement |
| 500 MB file design target | Backend currently 20 MiB default | F04 + F13 | Decide supported ceiling, align backend + proxy + UI contract |
| Global application search | Missing | F05 | Cross-resource search API with permissions and workspace scoping |
| Richer academic discovery | Existing Semantic Scholar path is narrower | F05 | Provider-neutral search contract + OpenAlex/Crossref/other adapters as required |
| Claim-centric evidence matrix | Retrieval exists, independent claim API absent | F06 | Claim/evidence/citation contract with provenance |
| Knowledge graph export | Missing | F06 | Export endpoint and bounded export formats |
| Research-plan edit/save/restore | Generate/get/versions/coverage/validate only | F07 | Mutation + version restore/compare semantics |
| Manuscript autosave/conflict handling | No explicit contract | F08 | Draft save, revision/version IDs, conflict detection, restore |
| Real AI detection | Heuristic baseline only | F09 + F20 | Real detector adapter, provider result normalization, usage accounting |
| Job retry action | Durable retry policy exists, API retry missing | F10 | Explicit retry endpoint with authorization/idempotency rules |
| Audit/activity user surface | Audit primitives exist, read-side product surface is partial | F12 + F13 | Safe user-facing activity projection, not raw debug logs |
| 2FA | Missing | F12 | TOTP/recovery-code model and flows |
| API tokens | Missing | F12 | Hashed token storage, scopes, expiry/revocation, last-used metadata |
| Full 21-page frontend | Only subset of routes exists | F13 | Complete production route/module implementation |
| Frontend contract/type generation | Production pipeline is incomplete | F13 + F16 | Generated TS contract or centralized verified DTO layer |
| Frontend integration hardening | Implemented | F14 | Session-scoped query cache isolation, typed API errors/status-aware retry, provider matrix UI, durable Job Center polling/retry/cancel, and tenant-isolation acceptance |
| Security/observability hardening | Implemented (code) | F15 | Request correlation, structured redaction, security headers, frontend sink/secret audit; deployment telemetry remains environment-specific |
| CI/CD release gates | Implemented (code) | F16 | Backend/frontend quality gates, migration upgrade/downgrade checks, real-backend E2E, security audit, Docker, release gate |
| Production smoke / external service verification | Implemented (code), runtime-pending | F17 | Reusable smoke runner/workflow with authenticated API and optional external-provider verification; requires deployment credentials |
| Failure/chaos/recovery | Implemented (code), runtime-pending | F18 | Provider fallback/recovery tests, stale-worker reclamation, storage failure coverage, repeatable recovery runner/workflow; live staging fault injection remains deployment-specific |

## F19 — Final Audit & Production Readiness

F19 is the final repository release-readiness gate after F18 recovery contracts and before production activation.

- Cross-platform final audit checks migration/release artifacts and repository secret hygiene.
- Frontend security audit is part of the final gate.
- Required operational scripts/workflows are verified.
- Runtime closure remains dependent on staging evidence.

## Cross-cutting F20 — External Service Provisioning & Provider Activation

**Status: Implemented (code), runtime-pending.**

F20 is an operational gate rather than another UI milestone.

It starts after F01 provider architecture and feeds F02/F04/F05/F09/F11/F15/F17.

### F20-A — AI access

**OpenRouter**
- Generation provider adapter.
- Optional embedding adapter.
- Model allowlist and explicit production defaults.
- Timeout/retry/fallback behavior.
- Provider usage mapping.
- Browser never receives the secret key.

**Real AI detection**
- Select one production provider after multilingual coverage, contract, cost, and data-retention review.
- Keep the provider behind the detection abstraction.
- Heuristic detection remains a deterministic baseline/testing fallback, not a production-equivalent detector.

### F20-B — Research discovery

- Semantic Scholar key for controlled production rate limits.
- OpenAlex key for higher-volume discovery/full-text workflows where needed.
- Crossref as a metadata source; its public REST API does not require an API key.
- Optional NCBI/PubMed integration for biomedical workflows.

All provider access stays server-side.

### F20-C — Storage

Choose exactly one primary production object-storage path first:
- Cloudflare R2 (S3-compatible), or
- AWS S3.

Required capabilities:
- private objects by default
- scoped credentials
- signed GET/PUT where appropriate
- key validation
- server-side authorization
- retention/lifecycle policy
- authoritative storage byte accounting

### F20-D — Transactional email

Choose one provider:
- Resend
- Postmark
- SendGrid
- another explicitly approved provider

Initial workflows:
- email verification
- password reset
- invitation
- important account/security notifications

Email delivery must be idempotent and must not log message bodies or secrets.

### F20-E — Billing

Choose one payment provider first. Stripe is the current roadmap candidate, while the backend remains provider-agnostic.

Required:
- checkout/session creation
- subscription lifecycle
- webhook signature verification
- event idempotency/inbox
- customer/subscription mapping
- cancellation reconciliation

Secret payment credentials remain server-side.

### F20-F — OAuth

Optional until social login is activated:
- Google OAuth credentials + callback
- GitHub OAuth credentials + callback

Use secure state/PKCE/callback validation.

### F20-G — Observability / abuse controls

Optional:
- Sentry
- Cloudflare Turnstile or equivalent

These remain provider-neutral behind configuration.

## External API priority

### Needed for the first production operational environment

| Service | Why | Secret/config |
|---|---|---|
| OpenRouter | LLM generation; can also provide embeddings | `OPENROUTER_API_KEY` |
| Semantic Scholar | Academic discovery | `SEMANTIC_SCHOLAR_API_KEY` |
| Object storage | Production file persistence | R2 or S3 credentials |
| Transactional email | Verification/reset/invitations | Provider key + verified sender/domain |
| AI detector | Real detection workflow | Provider key (provider TBD) |
| Billing | Paid SaaS lifecycle | Provider secret + webhook secret + catalog IDs |

### Needed when those features are enabled

| Service | Feature |
|---|---|
| Google OAuth | Google sign-in |
| GitHub OAuth | GitHub sign-in |
| OpenAlex | Higher-volume academic discovery/full text |
| Crossref | Metadata enrichment / DOI-oriented discovery |
| NCBI | PubMed/PMC biomedical workflows |
| Sentry | Production error telemetry |
| Turnstile | Auth abuse/bot mitigation |

## Secret-management rule

Never paste production secrets into chat or commit them to Git.

Use:
- local development: ignored `.env`
- CI: encrypted GitHub Actions secrets
- staging/production: platform secret manager

The repository only contains placeholders in `.env.example`.

## Acceptance rule

An external API is not integrated until:
1. adapter exists behind the provider abstraction
2. configuration is explicit
3. credentials are secret-managed
4. typed error mapping exists
5. timeout/retry policy is defined
6. usage/idempotency behavior is defined
7. at least one integration/smoke test exists
8. failure behavior is visible in the product

## Unified legacy Phase 12-14 bridge

The older product roadmap contained three persistence/integration milestones that were not
represented as standalone current F-phases. They are now tracked as one completed implementation
bridge on `phase123-integration`:

- Legacy Phase 12 — PDF Workspace persistence.
- Legacy Phase 13 — Research Canvas persistence.
- Legacy Phase 14 — File Intelligence → Evidence unification.

The implementation is documented in `docs/PHASE12_14_PERSISTENCE_EVIDENCE.md` and must still
pass local/backend/frontend acceptance before the later production runtime gates are closed.
