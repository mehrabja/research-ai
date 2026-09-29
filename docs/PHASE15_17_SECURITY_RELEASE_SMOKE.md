# Phase 15-17 — Security, Release Gates, Production Smoke

Date: 2026-09-29
Branch: phase123-integration

## Phase 15

Security and observability hardening includes:

- safe inbound request-ID validation and canonical response propagation
- request completion telemetry with method, path, status, duration, and correlation ID
- structured JSON logging with recursive secret redaction
- cross-origin isolation response headers
- static frontend security-sink and secret audit
- API tests covering the security/observability contracts

## Phase 16

The CI release gate includes:

- backend lint and mypy
- Alembic upgrade, head verification, downgrade, and upgrade
- backend application smoke import/health
- full backend tests
- frontend typecheck, lint, build, and unit tests
- frontend security audit
- Docker build
- frontend Playwright E2E against a real PostgreSQL + FastAPI runtime
- final release-gate job that depends on all required CI jobs

The E2E workflow sets BACKEND_URL (the variable consumed by the Next.js BFF), provisions PostgreSQL, applies migrations, starts FastAPI, waits for liveness, and then runs Playwright.

## Phase 17

A manual Production Smoke GitHub Actions workflow and cross-platform scripts/production_smoke.py runner are included.

Core runtime checks:

- liveness
- readiness
- OpenAPI
- X-Request-ID propagation
- authenticated /auth/me when a smoke token/key is supplied
- provider matrix and optional expected-provider assertions
- project listing when authenticated

Optional external provider checks:

- OpenRouter
- Semantic Scholar
- OpenAlex
- Crossref
- NCBI
- Unpaywall

External credentials are read only from environment variables or GitHub Environment secrets and are never printed.

## Runtime closure

Phase 17 becomes operationally closed only after the smoke workflow is executed against the actual deployment with its required credentials. The repository now contains the repeatable mechanism and release gate for that verification.
