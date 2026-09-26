\# Dependency policy (M36)



\## Principles



\- Pin versions in `pyproject.toml` with upper bounds.

\- Add a dependency only when the standard library or an existing

&#x20; dependency cannot reasonably cover the need.

\- Never add a dependency that requires a paid service to run tests.

\- Prefer pure-Python, widely-used, actively-maintained packages.



\## Runtime dependencies



| Package                | Purpose                    | Notes |

|------------------------|----------------------------|-------|

| SQLAlchemy             | ORM / Core                 | 2.x only |

| alembic                | migrations                 | schema versioning |

| psycopg\[binary]        | PostgreSQL driver          | v3 |

| pgvector               | vector type support        | HNSW/IVF |

| python-dotenv          | .env loading               | dev/local only |

| fastapi                | ASGI framework             | 0.115+ |

| uvicorn\[standard]      | ASGI server                | dev + prod |

| pydantic\[email]        | validation + email         | v2 |

| pydantic-settings      | env → Settings             | v2 |

| pyjwt                  | JWT encode/decode          | HS256 |

| argon2-cffi            | password hashing           | argon2id |



\## Development dependencies



| Package                | Purpose                    |

|------------------------|----------------------------|

| python-multipart       | file uploads               |

| pytest                 | test runner                |

| pytest-asyncio         | async tests                |

| httpx                  | TestClient transport       |

| pymupdf                | PDF extraction             |

| beautifulsoup4         | HTML extraction            |

| tiktoken               | token estimation           |

| ruff                   | linter + formatter         |

| mypy                   | static typing              |

| types-python-dateutil  | stubs                      |



\## Not added in M36 (deliberately)



\- `redis` — in-memory rate limiter covers single-instance. Multi-

&#x20; replica shared backend is a future concern.

\- `opentelemetry-\*` — tracing hooks are provider-neutral; a real

&#x20; backend belongs to a later milestone.

\- Any vendor SDK for payments, email, or LLM providers — owned by

&#x20; M39/M40.

\- `alembic` autogenerate helpers — migrations are hand-written.



\## Update policy



\- Run `pip list --outdated` manually; review security advisories.

\- Upgrade one package per PR, run full test suite, run migration gate.

\- Do not upgrade major versions without an ADR.



\## Removal policy



\- Any dependency that is no longer imported by `app/` or `tests/`

&#x20; must be removed from `pyproject.toml`.

\- Any dependency that duplicates the functionality of an existing

&#x20; dependency must be removed unless there is a documented reason.
## M37 dependency notes

M37 adds **no** runtime dependency.

- No payment provider SDK (Stripe / Paddle / PayPal / Braintree).
- No AI provider SDK.
- The `BillingProvider` Protocol is a pure in-tree interface.
- `FakeBillingProvider` is in-tree and dependency-free.