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


Release verification:

    make release-gate
    set SMOKE_BASE_URL=http://localhost:8000
    python scripts/production_smoke.py

The GitHub Actions workflow named Production Smoke is manual and reads deployment/provider credentials only from GitHub Environment secrets and variables.

## Zero-cost staging runtime

The repository includes a real staging-like Docker deployment for the self-hosted Windows GitHub runner.

    gh workflow run staging-deploy-smoke.yml --ref phase14-15-completion

This provisions PostgreSQL + pgvector, FastAPI, and the Next.js standalone frontend with the staging provider contract.

Additional operational gates:

    gh workflow run staging-chaos.yml --ref phase14-15-completion
    gh workflow run staging-backup-restore.yml --ref phase14-15-completion
    gh workflow run staging-release-evidence.yml --ref phase14-15-completion

GitHub CI, recovery, smoke, and backup workflows are configured for the self-hosted Windows runner so they do not depend on GitHub-hosted runner billing. The runner requires Python 3.11+, Node.js 20+, and Docker.
