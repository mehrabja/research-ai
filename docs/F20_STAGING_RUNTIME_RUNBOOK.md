# F20 — Staging Runtime Provisioning & Activation Runbook

Date: 2026-10-01
Branch: phase14-15-completion

## Purpose

This runbook closes the gap between repository-level provider implementation and a real
staging runtime. Production secrets must be stored only in the deployment platform's
secret manager or GitHub Actions Environment secrets.

The repository must never contain real credentials.

## 1. GitHub Environments

Create or verify these GitHub Environments:

- `staging`
- `production`

The manual workflows in this branch target the selected Environment, so Environment-scoped
secrets/variables are used automatically.

## 2. Current zero-cost staging provider routing

Set these Environment variables:

```text
GENERATION_PROVIDER=openrouter
EMBEDDING_PROVIDER=openrouter
TRANSLATION_PROVIDER=openrouter
SOURCE_DISCOVERY_PROVIDER=openalex
FILE_STORAGE_BACKEND=local
EMAIL_PROVIDER=resend
BILLING_PROVIDER=none
DETECTION_PROVIDER=sapling

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DETECTION_SAPLING_BASE_URL=https://api.sapling.ai/api/v1
```

OpenRouter is the paid generation/embedding/translation provider already funded by the
project owner. Sapling is used for AI detection through its free trial quota during staging.

The local storage backend is temporary. It will be moved to MinIO on the future Linux server.
Stripe remains disabled until a public staging URL exists for the webhook.

## 3. Current staging secrets

Store these as Environment secrets:

```text
OPENROUTER_API_KEY
OPENALEX_API_KEY
NCBI_API_KEY
SAPLING_API_KEY
RESEND_API_KEY
STRIPE_SECRET_KEY
```

Semantic Scholar can be added later when approval arrives.

Do not add storage credentials while `FILE_STORAGE_BACKEND=local`.

## 4. Current non-secret variables

```text
EMAIL_FROM
CROSSREF_MAILTO
UNPAYWALL_EMAIL
```

Stripe Price IDs can remain configured in the Environment, but they are not used while
`BILLING_PROVIDER=none`.

## 5. Deferred production prerequisites

These are intentionally deferred:

```text
SEMANTIC_SCHOLAR_API_KEY
STRIPE_WEBHOOK_SECRET
STORAGE_ACCESS_KEY_ID
STORAGE_SECRET_ACCESS_KEY
```

Originality.ai is also not active in the zero-cost staging configuration.

## 6. Deployment security settings

The deployed API should also have:

```text
APP_ENV=staging
DEBUG=false
AUTH_REQUIRE_VERIFIED_EMAIL=true
```

Use the real staging web/API origins for `CORS_ALLOWED_ORIGINS`.

Use a strong random `JWT_SECRET_KEY` stored in the deployment secret manager.

## 7. Execute F20 activation

From GitHub Actions:

**Actions → Provider Activation → Run workflow**

Select:

```text
environment: staging
strict: true
external: true
```

The gate verifies:

- configured generation / embedding / translation routing
- OpenAlex configuration and external connectivity
- Sapling account status through the non-billable `/api/v1/account/status` endpoint
- transactional email configuration
- optional NCBI/Crossref checks

The Sapling account-status endpoint does not consume the detector's billable/trial character
allowance. Actual detection requests use `POST /api/v1/aidetect`.

## 8. Execute F17 production smoke

After activation passes, run:

**Actions → Production Smoke → Run workflow**

Select:

```text
environment: staging
```

Set these Environment variables:

```text
PRODUCTION_SMOKE_EXPECT_PROVIDER=generation=openrouter;embedding=openrouter;translation=openrouter;detection=sapling;source_discovery=openalex

PRODUCTION_SMOKE_VERIFY_SAPLING=true
PRODUCTION_SMOKE_VERIFY_OPENROUTER=true
PRODUCTION_SMOKE_VERIFY_OPENALEX=true
```

Set these Environment secrets once a public staging deployment exists:

```text
PRODUCTION_SMOKE_BASE_URL
PRODUCTION_SMOKE_ACCESS_TOKEN
```

A scoped API key can be used instead of the access token:

```text
PRODUCTION_SMOKE_API_KEY
```

Do not configure both unless there is a specific reason; the smoke helper prefers the access
token.

The smoke should report:

```text
Production smoke: PASS
```

and include the configured provider matrix and request-correlation IDs.

## 9. Evidence required before production

Keep the following as release evidence:

1. Provider Activation — staging — strict=true — external=true — PASS
2. Production Smoke — staging — PASS
3. Frontend/backend local gates — PASS
4. F18 recovery suite — PASS
5. Final audit — PASS

Only after staging evidence is clean should the same provider/secret contract be applied to
the production Environment.

## 10. CLI alternative

When GitHub CLI is installed and authenticated:

```bat
gh workflow run provider-activation.yml -f environment=staging -f strict=true -f external=true
gh workflow run production-smoke.yml -f environment=staging
```

Secrets and Environment variables must still be configured in GitHub before these workflows
can pass.

## Security rule

Never paste any real API key, webhook secret, OAuth client secret, storage secret, JWT secret,
or access token into chat, source control, issue comments, or logs.
