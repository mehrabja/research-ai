\# Production deployment (M36)



This document describes the production configuration contract for

`research-ai`. It is scoped to M36 (infrastructure, security,

reliability).



\## 1. Environment



The canonical env file location is the monorepo root: `<repo>/.env`.

`app.core.config.Settings` loads it automatically. Copy

`.env.example` and fill in the required values.



Required in production:



\- `APP\_ENV=production`

\- `DEBUG=false`

\- `JWT\_SECRET\_KEY` — at least 32 bytes, not the dev default

\- `DATABASE\_URL`



Fail-closed validation at startup:



\- `APP\_ENV=production` with `DEBUG=true` → refused

\- `APP\_ENV=production` with wildcard CORS → refused

\- `JWT\_SECRET\_KEY` unchanged from the dev default → refused

\- `JWT\_SECRET\_KEY` shorter than 32 bytes → refused



\## 2. Database



`DATABASE\_URL` must use `postgresql+psycopg://`.



Production pool settings (per worker process):



\- `DB\_POOL\_SIZE` — default 5

\- `DB\_MAX\_OVERFLOW` — default 10

\- `DB\_POOL\_TIMEOUT\_SECONDS` — default 30

\- `DB\_POOL\_RECYCLE\_SECONDS` — default 1800

\- `DB\_CONNECT\_TIMEOUT\_SECONDS` — default 10

\- `DB\_STATEMENT\_TIMEOUT\_MS` — default 30000



`health\_engine` uses `NullPool` with a 3-second connect timeout.



\## 3. Migrations



Migrations run with `alembic upgrade head`. Always run the migration

gate before deploying:



&#x20;   alembic upgrade head

&#x20;   alembic current

&#x20;   alembic heads

&#x20;   alembic downgrade -1

&#x20;   alembic upgrade head



\## 4. Process model



\- API: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

\- Worker: `python -m app.workers`

\- Both processes must be supervised by a process manager that

&#x20; forwards `SIGTERM` for graceful shutdown.



\## 5. Health checks



\- `/api/v1/health/live` — liveness only, no dependency checks

\- `/api/v1/health/ready` — configuration + database + queue



Point load balancer liveness probes at `/health/live` and readiness

probes at `/health/ready`.



\## 6. Shutdown semantics



The FastAPI lifespan hook disposes SQLAlchemy engine pools. It does

NOT drain in-flight HTTP requests or worker jobs. Request draining is

the process manager's responsibility.



The worker reacts to `SIGTERM`/`SIGINT` by setting a stop event and

exiting the poll loop without claiming new work.



\## 7. Configuration changes



Changing `Settings` requires a process restart. Readiness does not

hot-reload configuration.



\## 8. Logs



\- `LOG\_FORMAT=json` recommended in production

\- `LOG\_LEVEL=INFO`

\- Logs include `request\_id` automatically

\- Never logs: Authorization headers, DB URLs with credentials,

&#x20; provider API keys, full manuscript/evidence content

## 9. SaaS / billing configuration (M37)

Additional environment variables:

- `BILLING_PROVIDER` — one of `none` (default) or `fake`.
  Real providers are configured in M40.

No real payment provider SDK is imported by M37, and no production
payment credential is expected in this milestone.

## 10. Workspace provisioning

Every new user is provisioned a personal workspace on first
resource creation (`create_project` / `create_report`) via
`ensure_default_workspace`.  Provisioning creates:

1. `workspaces` row (owner_user_id = user.id)
2. `workspace_memberships` row (role = owner, status = active)
3. `subscriptions` row (plan = free, status = active,
   provider = `none`)

All three inserts happen in a single transaction; partial state
is impossible.