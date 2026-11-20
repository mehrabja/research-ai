# Open-source publication checklist

This checklist is for the first public release. It is intentionally conservative because the repository is currently private and includes authentication, file ingestion, external providers, and research-content workflows.

## 1. Security and repository history

- [ ] Run the committed Secret Scan workflow and require a successful Gitleaks CLI scan across all locally fetched refs (`git --log-opts=--all`), not only the current branch or first-parent history.
- [ ] Manual fallback from the repository root: `docker run --rm -v "$PWD:/path" -w /path ghcr.io/gitleaks/gitleaks:v8.30.1 git --log-opts=--all --redact --no-banner .`.
- [ ] Review all findings manually. Do not publish if a credential or private key is found.
- [ ] If a real secret was ever committed, revoke or rotate it first. Removing a file from the latest tree does not remove it from Git history.
- [ ] Review all environment templates and confirm they contain placeholders only.
- [ ] Review Actions workflows and third-party actions; pin actions to verified immutable commit SHAs where practical.
- [ ] Enable GitHub Secret Scanning and Push Protection after the repository becomes public.
- [ ] Enable Dependabot alerts and code scanning. Review and triage all new alerts.
- [ ] Confirm the private vulnerability reporting channel is enabled and tested.

## 2. License and supply chain

- [ ] Confirm the project owner intends to license the complete project under Apache-2.0.
- [ ] Check that root LICENSE and apps/api/LICENSE are identical.
- [ ] Complete the Python and npm direct/transitive license inventory.
- [ ] Review LGPL requirements for psycopg-binary and any other copyleft dependencies.
- [ ] Confirm all datasets, test data, fonts, logos, images, and screenshots may be redistributed.
- [ ] Generate and commit apps/web/package-lock.json.
- [ ] Switch CI from npm install to npm ci after the lockfile is committed.
- [ ] Run npm audit and review Python dependency vulnerability reports.
- [ ] Generate an SBOM for the exact release artifacts.

## 3. Engineering validation

- [ ] Run Ruff, mypy, backend unit/integration tests, frontend typecheck/unit tests, production build, Playwright tests, and Docker build.
- [ ] Validate the pypdf migration on representative text PDFs, scanned PDFs, malformed PDFs, and encrypted PDFs.
- [ ] Confirm PDF text extraction does not claim OCR support.
- [ ] Verify Alembic has a single intended head and that migrations work from a clean PostgreSQL 16 + pgvector database.
- [ ] Test the local setup instructions on a clean machine.
- [ ] Verify CI is green on the exact release candidate commit.
- [ ] Resolve or clearly mark open pull requests before the first release.

## 4. Public documentation and user safety

- [ ] Review README feature claims against docs/M39_M40_CAPABILITY_MATRIX.md.
- [ ] Add real sanitized screenshots from a demo deployment; do not publish private documents, names, tokens, or research data.
- [ ] Publish an architecture and data-flow description, including what is sent to external AI/literature providers.
- [ ] Explain that model outputs and generated citations require human verification.
- [ ] Document deployment secrets, HTTPS, secure cookies, backups, retention, deletion, and provider configuration.
- [ ] Add a real issue/PR process and test the private vulnerability report path.
- [ ] Prepare a small opt-in tester group and a feedback procedure. Do not invite users to upload confidential or regulated content.

## 5. Release

After every blocking item above has been resolved:

1. Merge the reviewed OSS preparation pull request.
2. Change repository visibility to public only after one final secret and content review.
3. Create a clearly labeled pre-release such as v0.1.0-beta.
4. Publish release notes that distinguish verified capabilities from partial or provider-dependent ones.
5. Invite a small number of testers and monitor issues.
6. Record truthful usage signals over time: unique users, stars, forks, external contributions, issue triage, releases, and dependency downloads where available.

Do not claim wide adoption or critical ecosystem importance before those signals exist.
