# Research AI

**An evidence-grounded research workspace for discovering literature, organizing source material, building traceable evidence, and developing research manuscripts.**

[![CI](https://github.com/mehrabja/research-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/mehrabja/research-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Research AI is a full-stack research-workflow application. It brings literature discovery, document ingestion, evidence retrieval, research planning, manuscript workflows, and collaboration into one workspace. It is designed around traceability: research material is stored as sources and files, processed into structured evidence, and connected to reports and manuscript work.

> **Project status:** Early-stage open-source preparation. Several capabilities are implemented, while others remain partial or require external provider configuration. This repository is not a claim of production certification, research validity, or guaranteed output quality. See the [capability matrix](docs/M39_M40_CAPABILITY_MATRIX.md) before relying on any individual feature.

## What it is designed to do

- **Discover and organize research:** create projects and reports, discover literature, and manage source records.
- **Ingest source material:** extract text from PDF, HTML, and plain-text sources; normalize content; preserve page boundaries and provenance.
- **Build searchable evidence:** chunk source material, create embeddings, retrieve relevant context, and support RAG-style research workflows.
- **Connect knowledge:** represent research concepts and technical facts through knowledge-graph and code/data-intelligence components.
- **Plan and write:** develop research plans, work with manuscript drafts and versions, and support translation and language-humanization workflows.
- **Collaborate and operate:** provide workspaces, role-aware access, background jobs, file handling, usage accounting, and operational controls.

The detailed capability matrix labels individual areas as implemented, partial, missing, or not configured. Treat those labels as the source of truth; the summary above describes the product direction and code areas, not a promise that every path is complete.

## Architecture

The system is organized as a Next.js frontend, a FastAPI backend, domain and service layers, background workers, and PostgreSQL with pgvector.

~~~mermaid
flowchart TD
    U[Researcher] --> WEB[Next.js 16 / React 19]
    WEB --> BFF[Same-origin API routes / BFF]
    BFF --> API[FastAPI REST API]
    API --> DOMAIN[Domain and application services]
    API --> DB[(PostgreSQL 16 + pgvector)]
    DOMAIN --> JOBS[Durable job queue]
    JOBS --> WORKERS[Background workers]
    WORKERS --> INT[Provider and document integrations]
    INT --> EXT[External literature / AI providers]
    DOMAIN --> FILES[File storage adapter]
    FILES --> STORE[(Local storage or S3-compatible storage)]
    DOMAIN --> EVIDENCE[Sources, chunks, citations, knowledge graph]
    EVIDENCE --> DB
~~~

### Main technologies

| Layer | Technologies |
|---|---|
| Web | Next.js, React, TypeScript, TanStack Query |
| API | Python 3.11+, FastAPI, Pydantic |
| Data | PostgreSQL 16, SQLAlchemy, Alembic, pgvector |
| Research processing | Document extraction, chunking, embeddings, retrieval, provenance |
| Background work | Database-backed jobs and worker processes |
| Testing | Pytest, Ruff, mypy, Vitest, Playwright |
| Local infrastructure | Docker Compose |

## Repository layout

~~~text
.
├── apps/
│   ├── api/                 # FastAPI application, domain, services, workers and tests
│   └── web/                 # Next.js frontend and browser tests
├── docs/                    # Architecture, operations, capability and release notes
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── docker-compose.dev.yml   # Local PostgreSQL + pgvector
├── .env.example             # Placeholder-only local configuration
├── CONTRIBUTING.md
├── SECURITY.md
└── LICENSE
~~~

## Local development

### Prerequisites

- Python 3.11 or newer
- Node.js 20.9 or newer
- Docker with Docker Compose
- PostgreSQL 16 with the pgvector extension (the Compose file provides this)
- Git

External AI, embedding, email, OAuth, or billing integrations may require provider credentials. They are intentionally not bundled in the repository.

### 1. Clone and configure

~~~bash
git clone https://github.com/mehrabja/research-ai.git
cd research-ai
cp .env.example .env
~~~

The checked-in environment file contains development placeholders only. Never replace them with production credentials in a committed file. The default development JWT secret is not suitable for deployment.

### 2. Start PostgreSQL

~~~bash
docker compose -f docker-compose.dev.yml up -d postgres
~~~

The default local database values in .env.example match the Compose defaults. Change both consistently when using a different local password or database name.

### 3. Install and start the API

~~~bash
cd apps/api
python -m venv .venv
~~~

Activate the virtual environment, then run:

~~~bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
~~~

The API runs at http://localhost:8000. OpenAPI documentation is available at http://localhost:8000/docs.

### 4. Install and start the web app

In a second terminal, from the repository root:

~~~bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
~~~

The web app runs at http://localhost:3000. Its local BFF points to http://localhost:8000 by default.

## Tests and quality checks

Backend checks:

~~~bash
cd apps/api
ruff check app tests
mypy app
pytest tests -q
~~~

Frontend checks:

~~~bash
cd apps/web
npm run typecheck
npm run test:unit
npm run build
~~~

End-to-end tests require the API, PostgreSQL, and a Playwright browser. From apps/web, run npm run test:e2e after configuring and starting the test services.

The CI workflow also runs database migrations, a migration downgrade/upgrade check, an API smoke test, and a Docker build. A successful local run should be recorded before creating a tagged release.

## Configuration and external services

- Copy .env.example to .env for local development. Keep real secrets out of Git.
- Provider credentials are optional for some local workflows, but AI generation, embeddings, translation, email delivery, OAuth, object storage, and billing are not fully configured by default.
- FILE_STORAGE_BACKEND=local is suitable for local development. S3-compatible storage requires separately configured credentials and deployment review.
- Production startup has fail-closed checks for selected unsafe settings. Do not treat those checks as a substitute for a deployment security review.

## Security and privacy

Please read [SECURITY.md](SECURITY.md) before reporting a vulnerability. Do not commit API keys, database URLs, OAuth secrets, JWT secrets, customer data, research documents, or backups. Do not upload confidential or personally identifiable research material to a test deployment unless you have verified its data-handling arrangements.

## Screenshots and demos

No sanitized product screenshots or public demo environment are included in this repository snapshot. The architecture diagram above is generated from the documented component boundaries. Real screenshots should be added only after a running demo has been captured and all names, documents, tokens, and other private data have been removed.

## Current limitations

- The capability matrix includes partial and missing areas; not all roadmap items are complete.
- Several integrations require external credentials and provider-specific verification.
- The frontend package currently has no committed npm lockfile. A reproducible package-lock.json and npm ci workflow are required before a stable public release.
- Public adoption, downloads, external contributors, and third-party usage have not yet been established or measured.
- PDF text extraction has been moved from PyMuPDF to pypdf in the OSS preparation branch; the full backend and end-to-end test suites must pass against this change before release.

## Contributing

Contributions are welcome after the public repository is opened. Start with [CONTRIBUTING.md](CONTRIBUTING.md), review open issues, and submit changes as focused pull requests. For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## License

Research AI is proposed to be distributed under the MIT License. See [LICENSE](LICENSE). Third-party dependencies retain their own licenses; see [docs/LICENSING_AUDIT.md](docs/LICENSING_AUDIT.md) and [docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).
