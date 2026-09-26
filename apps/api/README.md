\# research-ai — API



Backend for the evidence-grounded research report generator.



\## Local setup



Requirements:



\- Python 3.11+

\- PostgreSQL 16 with the `pgvector` extension



Steps:



&#x20;   cd apps/api

&#x20;   python -m venv .venv

&#x20;   .venv\\Scripts\\activate            # Windows

&#x20;   # source .venv/bin/activate       # macOS / Linux



&#x20;   pip install -e ".\[dev]"



&#x20;   # Configure environment

&#x20;   copy ..\\..\\.env.example ..\\..\\.env

&#x20;   # edit ..\\..\\.env and set DATABASE\_URL



&#x20;   alembic upgrade head



&#x20;   uvicorn app.main:app --reload



\## Tests



&#x20;   pytest tests -q



Focused:



&#x20;   pytest tests/core -q

&#x20;   pytest tests/workers -q

&#x20;   pytest tests/api -q



\## Static checks



&#x20;   ruff check app tests

&#x20;   mypy app



\## Docker (local dev)



&#x20;   docker compose up --build



Starts Postgres + pgvector and the API on port 8000.



\## Scripts



&#x20;   python scripts/smoke\_test.py

&#x20;   python scripts/backup\_db.py

&#x20;   python scripts/verify\_backup.py <file>

&#x20;   python scripts/restore\_db.py <file> --target-url ... --yes



\## Documentation



\- `docs/production.md` — production configuration contract

\- `docs/security.md` — security model

\- `docs/operations.md` — runbook

\- `docs/backup-restore.md` — backup and restore



\## Environment



The canonical env file lives at the monorepo root: `<repo>/.env`.

See `.env.example` for the full variable list.



Production validation is fail-closed:



\- `APP\_ENV=production` with `DEBUG=true` → refused

\- Wildcard CORS in production → refused

\- Weak or default `JWT\_SECRET\_KEY` in production → refused

