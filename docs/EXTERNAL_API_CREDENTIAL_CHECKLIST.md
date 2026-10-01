# Research-AI — External API / Credential Checklist

Date: 2026-09-27
Branch: feature/m14-humanization

This file answers: what external APIs/services are actually needed for production.

## Current zero-cost staging contract

Staging currently provisions:

- OpenRouter for generation, embeddings, and translation.
- OpenAlex for source discovery.
- Sapling for AI detection.
- Resend for transactional email.
- Local filesystem storage.
- Billing disabled (`BILLING_PROVIDER=none`).

Semantic Scholar, MinIO/S3 storage, and Stripe billing are intentionally deferred from this zero-cost staging contract.

## 1. OpenRouter — first priority

Use OpenRouter as the server-side gateway for LLM generation.

```
Browser -> FastAPI -> provider registry -> OpenRouter -> model
```

Never call OpenRouter directly from browser code.

Initial configuration:

```
OPENROUTER_API_KEY=<secret>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

OpenRouter supports chat completions and embeddings. Its model catalog can be queried server-side,
but production model selection should be controlled by backend policy/allowlists.

For embeddings, validate a compatible model/dimension before switching the existing 1536-dimensional
pgvector contract.

## 2. Academic discovery

### Semantic Scholar — recommended

```
SEMANTIC_SCHOLAR_API_KEY=<secret>
```

The backend already has a Semantic Scholar adapter. A production key provides a more controlled
rate-limit budget.

### OpenAlex — recommended for scale/diversity

```
OPENALEX_API_KEY=<secret>
```

Use when higher-volume discovery/full-text workflows justify another source.

### Crossref — standard REST needs no API key

Configure a descriptive User-Agent and contact email:

```
CROSSREF_MAILTO=<your-email>
```

### NCBI/PubMed — optional

Only needed when biomedical literature is a first-class product domain.

## 3. Production file storage

Choose one primary object-storage backend.

### Cloudflare R2

```
STORAGE_ENDPOINT=<R2 S3 endpoint>
STORAGE_ACCESS_KEY_ID=<secret>
STORAGE_SECRET_ACCESS_KEY=<secret>
STORAGE_BUCKET=<bucket>
```

### AWS S3

Equivalent S3 credentials/configuration.

Production research files should not depend on local disk.

## 4. Transactional email

Choose one provider.

Initial candidate:

```
RESEND_API_KEY=<secret>
EMAIL_FROM=<verified sender>
EMAIL_REPLY_TO=<optional>
```

Workflows:
- email verification
- password reset
- invitations
- security notifications

Delivery must be idempotent and message bodies must not be written to logs.

## 5. Billing

Choose one provider first.

Current roadmap candidate:

```
STRIPE_SECRET_KEY=<secret>
STRIPE_WEBHOOK_SECRET=<secret>
STRIPE_PUBLISHABLE_KEY=<public value only if browser use is required>
STRIPE_PRICE_<PLAN>=<price id>
```

Backend owns checkout creation and webhook processing.

## 6. OAuth

Only needed when social login is activated.

### Google

```
GOOGLE_OAUTH_CLIENT_ID=<public id>
GOOGLE_OAUTH_CLIENT_SECRET=<secret>
GOOGLE_OAUTH_REDIRECT_URI=<callback>
```

### GitHub

```
GITHUB_OAUTH_CLIENT_ID=<public id>
GITHUB_OAUTH_CLIENT_SECRET=<secret>
GITHUB_OAUTH_REDIRECT_URI=<callback>
```

Use secure state/PKCE/callback validation.

## 7. Real AI detection

The current detector is a heuristic baseline, not a production external detector.

Required:
- provider with language coverage matching the multilingual roadmap
- API key
- typed response mapping
- provenance fields
- usage/cost recording
- explicit handling of probabilistic scores

Vendor accuracy claims must be benchmarked internally before becoming a production acceptance gate.

## 8. Optional operational services

- Sentry DSN for production error telemetry.
- Cloudflare Turnstile or equivalent for auth abuse/bot mitigation.
- Additional literature providers if product usage justifies them.

## 9. Services you do not need to buy

No separate external API is required for:
- Next.js/frontend runtime
- PostgreSQL
- JWT primitives
- provider fallback logic
- durable job persistence
- existing RAG core
- existing knowledge-graph core

These are application/backend capabilities.

## 10. Suggested credential acquisition order

1. OpenRouter
2. Semantic Scholar
3. R2 or S3
4. Resend
5. AI detector
6. Stripe
7. Google/GitHub OAuth when enabled
8. OpenAlex / Crossref / NCBI when their use cases are activated

## 11. Secret rule

Never paste production keys into chat or commit them to Git.

Use local ignored `.env`, GitHub Actions encrypted secrets, and the deployment platform's secret manager.
