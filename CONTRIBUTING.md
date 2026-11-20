# Contributing

Thank you for considering a contribution to Research AI. This project is being prepared for its first public release. Until the repository is public, use this guide as the proposed contribution process.

## Before opening an issue

- Search existing issues and pull requests for the same problem.
- For a substantial feature, open a discussion or feature request first so the scope can be agreed before implementation.
- Never publish credentials, private research documents, customer data, or vulnerability details in a public issue.

## Development setup

Follow the setup steps in the root README. The current development stack requires Python 3.11+, Node.js 20.9+, Docker Compose, and PostgreSQL 16 with pgvector.

### Backend

From apps/api, activate your virtual environment and run:

~~~bash
pip install -e ".[dev]"
alembic upgrade head
ruff check app tests
mypy app
pytest tests -q
~~~

### Frontend

From apps/web, run:

~~~bash
npm install
npm run typecheck
npm run test:unit
npm run build
~~~

The Playwright end-to-end suite requires the API and a PostgreSQL test database to be running. Run npm run test:e2e from apps/web after configuring the test environment.

## Pull requests

- Keep each pull request focused and explain the user or maintainer problem it solves.
- Describe the design choice and any alternatives considered.
- Add or update tests for behavior changes, bug fixes, authorization boundaries, and error paths.
- Update documentation and the capability matrix when behavior or project status changes.
- Include migration notes when database schema or environment variables change.
- Do not commit generated caches, local databases, backups, .env files, downloaded research papers, or private datasets.
- Do not weaken security checks just to make a test pass.
- Keep public claims aligned with verified implementation. Mark incomplete or provider-dependent behavior as partial.
- Ensure CI passes before requesting review. If a check cannot run locally, say so explicitly in the pull request.

## Commit and review expectations

Use clear commit messages such as feat(area): add capability or fix(area): correct behavior. Keep unrelated formatting changes out of functional pull requests. Maintainers may request changes, split a pull request, or close work that does not match the project scope.

## Licensing of contributions

By submitting a contribution, you agree that it may be distributed under the repository's Apache-2.0 license. You must have the right to submit the code, documentation, and other material, and must identify third-party material and its license. Do not submit copied proprietary code or content without permission.

## Security reports

Do not report vulnerabilities in public issues or pull requests. Follow the private reporting instructions in SECURITY.md.
