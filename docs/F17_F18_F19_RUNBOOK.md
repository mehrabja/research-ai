# F17–F19 Runtime Runbook

This branch contains a repeatable staging runtime on a self-hosted Windows GitHub runner.

## F17 — Staging deployment and production smoke

Run:

`gh workflow run staging-deploy-smoke.yml --ref phase14-15-completion`

The workflow:
- builds PostgreSQL, FastAPI, and Next.js containers
- provisions environment configuration from GitHub Environment secrets/variables
- creates an ephemeral pre-verified smoke account
- runs authenticated API smoke, provider-matrix checks, refresh/logout checks, and web security-header checks

The stack remains running at:
- API: `http://127.0.0.1:18000`
- Web: `http://127.0.0.1:13000`

## F18 — Live recovery

With staging running:

`gh workflow run staging-chaos.yml --ref phase14-15-completion`

The workflow intentionally stops and restarts:
- FastAPI
- PostgreSQL

It verifies readiness failure during the fault and recovery after restart. Provider retry/fallback fault classes remain covered by the deterministic Phase 18 suite.

## Backup / restore evidence

Run:

`gh workflow run staging-backup-restore.yml --ref phase14-15-completion`

The workflow takes a custom-format PostgreSQL dump from the running staging database and restores it into a disposable verification database.

## F19 — Final evidence

Run:

`gh workflow run staging-release-evidence.yml --ref phase14-15-completion`

The evidence workflow runs the repository final audit, F17 smoke, F18 live recovery, and backup/restore verification, then writes a local release-evidence file.

## Production transition

Public staging/production hosting, MinIO object storage, Semantic Scholar production credentials, Stripe billing, and webhook delivery remain separate deployment tasks.
