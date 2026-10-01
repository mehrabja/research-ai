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

## 2. Provider routing variables

For the first real operational environment, set these Environment variables:

```text
GENERATION_PROVIDER=openrouter
EMBEDDING_PROVIDER=openrouter
TRANSLATION_PROVIDER=openrouter
SOURCE_DISCOVERY_PROVIDER=semantic_scholar
FILE_STORAGE_BACKEND=s3
EMAIL_PROVIDER=resend
BILLING_PROVIDER=stripe
DETECTION_PROVIDER=originality

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DETECTION_ORIGINALITY_BASE_URL=https://api.originality.ai/api/v3
STORAGE_REGION=auto
STORAGE_PATH_STYLE=true
STRIPE_API_BASE_URL=https://api.stripe.com/v1
DETECTION_API_BASE_URL=
```

Set `OPENROUTER_BASE_URL`, `DETECTION_ORIGINALITY_BASE_URL`, and `STRIPE_API_BASE_URL`
only as needed when using the documented defaults.

## 3. Required secrets

Store the following as Environment secrets, not variables:

```text
OPENROUTER_API_KEY
SEMANTIC_SCHOLAR_API_KEY
AI_DETECTION_API_KEY

STORAGE_ACCESS_KEY_ID
STORAGE_SECRET_ACCESS_KEY

RESEND_API_KEY

STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

For OpenAI-backed embedding/translation/generation instead of OpenRouter, provide the
corresponding:

```text
GENERATION_OPENAI_API_KEY
EMBEDDING_OPENAI_API_KEY
```

Only configure those when the corresponding provider routing variable is `openai`.

## 4. Required non-secret variables

```text
STORAGE_ENDPOINT
STORAGE_BUCKET

EMAIL_FROM

STRIPE_PRICE_IDS
CROSSREF_MAILTO
UNPAYWALL_EMAIL
```

For Stripe, `STRIPE_PRICE_IDS` uses the application's existing format:

```text
plan_code=price_xxx;another_plan=price_yyy
```

`CROSSREF_MAILTO` and `UNPAYWALL_EMAIL` should be real operational contact addresses.

## 5. Deployment security settings

The deployed API should also have:

```text
APP_ENV=staging
DEBUG=false
FILE_MALWARE_SCAN_MODE=required
AUTH_REQUIRE_VERIFIED_EMAIL=true
```

Use the real staging web/API origins for `CORS_ALLOWED_ORIGINS`; do not use a wildcard in a
production environment.

Use a strong random `JWT_SECRET_KEY` stored in the deployment secret manager.

## 6. Execute F20 activation

From GitHub Actions:

**Actions → Provider Activation → Run workflow**

Select:

```text
environment: staging
strict: true
external: true
```

The gate now verifies:

- configured generation / embedding / translation routing
- Semantic Scholar credentials
- S3 configuration
- transactional email configuration
- Stripe configuration
- Originality.ai activation
- Originality.ai account balance via the read-only `/api/v3/account/balance` endpoint
- read-only Stripe balance verification
- optional discovery-provider checks

Originality.ai documents the V3 account-balance endpoint as `GET /api/v3/account/balance`
authenticated with `X-OAI-API-KEY`; it returns the available `credits` and
`subscriptionCredits`. The Stripe balance endpoint is `GET /v1/balance` and is read-only.

## 7. Execute F17 production smoke

After activation passes, run:

**Actions → Production Smoke → Run workflow**

Select:

```text
environment: staging
```

Set these Environment variables:

```text
PRODUCTION_SMOKE_EXPECT_PROVIDER=generation=openrouter;embedding=openrouter;translation=openrouter;detection=originality;source_discovery=semantic_scholar

PRODUCTION_SMOKE_VERIFY_ORIGINALITY=true
PRODUCTION_SMOKE_VERIFY_OPENROUTER=true
PRODUCTION_SMOKE_VERIFY_SEMANTIC_SCHOLAR=true
```

Set these Environment secrets:

```text
PRODUCTION_SMOKE_BASE_URL
PRODUCTION_SMOKE_ACCESS_TOKEN
```

A scoped API key can be used instead of the access token:

```text
PRODUCTION_SMOKE_API_KEY
```

Do not configure both unless there is a specific reason; the smoke helper prefers the
access token.

The smoke must report:

```text
Production smoke: PASS
```

and should include the configured provider matrix and request-correlation IDs.

## 8. Optional providers

Enable only when the corresponding product feature is actually deployed:

```text
OPENALEX_API_KEY
NCBI_API_KEY
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
GITHUB_OAUTH_CLIENT_ID
GITHUB_OAUTH_CLIENT_SECRET
SENTRY_DSN
TURNSTILE_SECRET_KEY
```

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
