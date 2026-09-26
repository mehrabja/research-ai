\# Security model (M36)



\## 1. Authentication



\- JWT bearer tokens, HS256, validated issuer/audience/type/alg

\- Access tokens expire after `JWT\_ACCESS\_TOKEN\_EXPIRE\_MINUTES` (default 30)

\- Argon2id password hashing

\- Login throttling via `app.services.rate\_limit` (per-email + per-IP)



\## 2. Authorization



\- All endpoints under `/api/v1` require a valid bearer token except

&#x20; `/health`, `/health/live`, `/health/ready`, `/health/db`

\- Ownership is enforced at the service layer

\- Unauthorized cross-user access is normalized to `404 Not Found`



\## 3. Request hardening



\- `BodyLimitMiddleware` rejects oversized bodies with 413 before the

&#x20; endpoint runs. Content-Length must be a strict `\[0-9]+` string.

\- `GlobalRateLimitMiddleware` applies a per-IP limit

\- Per-user / per-endpoint limits are enforced via

&#x20; `app.api.rate\_limit\_deps`

\- `TrustedHostMiddleware` rejects disallowed Host headers when

&#x20; `TRUSTED\_HOSTS` is set explicitly



\## 4. Client IP resolution



`app.core.client\_ip.get\_scope\_client\_ip` resolves the effective

client IP. X-Forwarded-For is only trusted when the direct peer is in

`TRUSTED\_PROXIES`. Otherwise XFF is ignored entirely.



\## 5. Secrets



\- `app.core.secrets.SecretResolver` is the provider-neutral contract

\- Default implementation is `EnvSecretResolver`

\- No secret ever appears in `repr(Settings)`, `model\_dump`, logs,

&#x20; API responses, or error envelopes



\## 6. Logging privacy



\- `app.core.logging.redact` masks sensitive field names and bearer

&#x20; tokens / DB URLs

\- Request IDs are correlation-only; never used as identity or as

&#x20; input to deterministic hashes



\## 7. Error envelopes



All errors use the shape:



&#x20;   {"error": {"code": ..., "message": ..., "request\_id": ...}}



429 responses additionally include `retry\_after` (int seconds) and

the `Retry-After` header.



Production responses never include stack traces, SQL statements,

filesystem paths, or credential material.



\## 8. Rate limiting scope



The default backend `InMemoryRateLimitBackend` is per-process. It is

correct for a single API replica. Multi-replica deployments MUST

provide a shared backend implementing `RateLimitBackend` (Redis or

similar). Redis is intentionally not added in M36.



\## 9. Report a vulnerability



Contact the maintainers privately. Do not open a public issue.

