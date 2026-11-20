# Self-hosted CI / staging operations

The repository's CI and runtime verification workflows are configured to run on:

```text
self-hosted
windows
x64
```

The runner must be online for push, pull-request, manual, and scheduled workflows. The machine must provide:

- Python 3.11 via the `py` launcher for full CI.
- Node.js 20+ and npm.
- Docker Desktop/Engine with Linux containers enabled.

`Provider Activation` can use the existing system Python because it only runs its standalone activation checker.

`CI`, `Chaos & Recovery`, `Production Smoke`, backup, and staging workflows are self-hosted. This avoids GitHub-hosted runner execution for this repository's operational workflows.

## Full CI

`CI` covers backend lint/typecheck/migrations/tests, frontend typecheck/lint/build/unit tests, Docker image builds, Playwright E2E, and the repository release gate.

PostgreSQL is started as a disposable Docker container by the Windows CI helpers instead of using GitHub-hosted service containers.

## Staging

`Staging Deploy & Smoke` creates a real local staging stack with PostgreSQL, FastAPI, and Next.js, using the `staging` Environment secrets.

`Staging Chaos & Recovery` injects live API and PostgreSQL interruptions and verifies readiness recovery.

`Staging Backup & Restore Evidence` validates a custom-format database backup by restoring it into a disposable verification database.

`Staging Release Evidence` orchestrates final audit, F17, F18, and backup/restore in one release gate.

## Operational limitation

A self-hosted runner only executes while its host is online. Scheduled backup therefore depends on the runner machine being powered on and connected to GitHub at the scheduled time.
