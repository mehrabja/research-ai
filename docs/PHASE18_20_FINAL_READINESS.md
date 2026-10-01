# Phase 18-20 — Final Runtime Readiness

Date: 2026-10-01
Branch: phase14-15-completion

## Phase 18

The repository contains both deterministic recovery coverage and a live staging chaos workflow.
The live workflow runs on the self-hosted Windows runner and intentionally interrupts the FastAPI
and PostgreSQL containers, verifying readiness failure and recovery.

Provider timeout/429/5xx and worker recovery behavior remains covered by the repeatable Phase 18
test suite. Live production fault injection is never enabled; staging is the required target.

## Phase 19

The final audit checks repository hygiene, required release artifacts, migration-related scripts,
and the frontend security audit.

Release evidence is recorded only after the staging release-evidence workflow has successfully
completed F17 smoke, F18 live recovery, backup/restore verification, and the repository final audit.

## Phase 20

Provider activation is environment-scoped and has been executed successfully on the self-hosted
Windows runner for staging.

Current staging routing:

- generation: openrouter
- embedding: openrouter
- translation: openrouter
- source discovery: openalex
- detection: sapling
- storage: local
- email: resend
- billing: none

OpenRouter, OpenAlex, NCBI, Crossref, Unpaywall, Resend, and Sapling have configuration/runtime
verification appropriate to the active staging contract. Semantic Scholar remains pending approval.

## Staging deployment

The real staging-like runtime is defined by `deploy/staging/docker-compose.yml` and uses:

- PostgreSQL + pgvector
- FastAPI API container
- Next.js standalone web container
- local persistent file storage

The self-hosted runner is used so GitHub-hosted runner billing does not block these workflows.

## Deferred production tasks

These are intentionally not part of the zero-cost staging closure:

- Linux server + MinIO object storage
- Semantic Scholar production credentials when approved
- public DNS/TLS deployment
- Stripe billing/webhook activation
- provider canary calls that consume external quotas beyond the read-only activation checks
