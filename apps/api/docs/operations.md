\# Operations runbook (M36)



\## Day-1 checks



After deploy:



&#x20;   curl -sf https://<host>/api/v1/health/live

&#x20;   curl -sf https://<host>/api/v1/health/ready

&#x20;   curl -sf https://<host>/api/v1/health/db



All three must return 200. `/health/live` must succeed even if the

database is down.



\## Deploy sequence



1\. Build the container image (`Dockerfile`)

2\. Run migrations (`alembic upgrade head`)

3\. Roll out the new API + worker processes

4\. Wait for `/health/ready` on new instances

5\. Drain old instances



\## Rollback



1\. Roll back application code

2\. Roll back the last migration only if it is non-destructive:

&#x20;  `alembic downgrade -1`

3\. Verify `/health/ready`



Never force-downgrade a data migration. Prefer forward fixes.



\## Worker operations



\- Start: `python -m app.workers`

\- Stop: send `SIGTERM`. The worker exits the poll loop without

&#x20; claiming new jobs. In-flight jobs finish their current attempt.

\- Recovery: stale jobs are reclaimed automatically based on

&#x20; `JOB\_PROCESSING\_TIMEOUT\_SECONDS`.



\## Incident diagnostics



For every incident, capture:



\- Request ID from response headers

\- Latest `/health/ready` response

\- Log lines matching the request ID

\- `alembic current` output



Do NOT capture:



\- JWT tokens

\- Database URLs with credentials

\- Provider API keys



\## Common issues



\### `/health/ready` returns 503



\- `checks.database == "unavailable"` — DB unreachable

\- `checks.queue == "unavailable"` — jobs table not accessible

\- Check `DATABASE\_URL` and Postgres logs



\### 429 storms



\- Inspect `RATE\_LIMIT\_\*` env values

\- Consider raising `RATE\_LIMIT\_GLOBAL\_PER\_MINUTE`

\- Check `TRUSTED\_PROXIES` — misconfigured proxies cause all traffic

&#x20; to share the proxy IP



\### 413 storms



\- Inspect `MAX\_REQUEST\_BYTES`

\- The client is exceeding the declared limit

