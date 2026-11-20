# Research-AI local staging stack

This directory defines the real staging-like runtime used by the self-hosted GitHub runner.

Ports:
- API: http://127.0.0.1:18000
- Web: http://127.0.0.1:13000

The stack uses PostgreSQL + pgvector, FastAPI, Next.js standalone, local file storage,
OpenRouter, OpenAlex, NCBI, Sapling, Resend, and billing disabled.

`scripts/staging_deploy.ps1` writes runtime secrets to `runtime/staging.env`.
`runtime/` is ignored by Git and must never be committed.
