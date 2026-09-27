# Research-AI

Research-AI is an evidence-grounded research workspace with a FastAPI backend and Next.js frontend.

## Repository layout

- `apps/api` — FastAPI, SQLAlchemy, Alembic, durable jobs, provider adapters, storage, usage metering, billing, auth.
- `apps/web` — Next.js application, typed BFF proxy, workspace UI, unit tests, Playwright E2E.
- `docs` — architecture, capability, dependency, milestone, and gap tracking.

## Local development

Backend:

    cd apps/api
    pip install -e ".[dev]"
    alembic upgrade head
    uvicorn app.main:app --reload

Frontend:

    cd apps/web
    npm install
    npm run dev

## Production configuration

External integrations are disabled by default and selected through environment configuration. Provider credentials remain server-side.

Production surfaces implemented on this branch include persistent auth sessions, password reset/email verification, TOTP MFA, Google/GitHub OAuth, personal API tokens, notifications, S3-compatible object storage, file folders, source-provider routing, durable job retries, Stripe billing/webhooks, workspace usage metering, versioned research plans, manuscript autosave/conflict handling, evidence matrix access, and knowledge-graph export.

## Verification commands

    make api-lint
    make api-typecheck
    make api-migrate
    make api-test
    make web-typecheck
    make web-build
    make web-test
    make web-e2e
