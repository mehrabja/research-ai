# Codex for Open Source — application preparation draft

**Prepared:** 2026-11-20  
**Project:** Research AI  
**GitHub account:** mehrabja  
**Repository:** https://github.com/mehrabja/research-ai

## Eligibility status at audit time

**Not ready to submit yet.** The repository is private in the audit snapshot, the OSS license and release preparation are on a separate branch, public adoption has not been established, and no public user/download metrics were verified.

OpenAI describes this program as support for maintainers of active open-source projects. It considers repository usage, ecosystem importance, and evidence of ongoing maintenance, including PR review, issue triage, release management, and core maintainer responsibilities. Selection and benefits are discretionary.

Official information:
- Program and application: https://openai.com/form/codex-for-oss/
- Program overview: https://developers.openai.com/community/codex-for-oss

## Verified repository evidence

The GitHub connector audit of this private repository found:

- The account owner is the repository owner and has admin, maintain, and push permissions.
- The repository's default branch at audit time was m39-production-capabilities.
- 12 pull requests were authored from the account during September–October 2026.
- Of those 12 pull requests, 2 were merged, 5 remained open, and 5 were closed without merging at the time of review.
- The PR set includes production frontend/BFF work, provider registry work, research-pipeline integration, security/authorization hardening, and CI/test-gate fixes.
- The current default-branch snapshot had an 887-file Git tree, including API, frontend, tests, migrations, and CI.
- The base branch includes a PostgreSQL 16 + pgvector CI service and backend/frontend test workflows.

The PR list is evidence of maintainer activity, not evidence of external contributors or adoption. The 5 open PRs and the age of the latest base-branch commits should be reviewed before applying.

## Evidence not yet available

Do not invent or estimate these fields. Fill them only with verifiable public data after release:

- Public repository URL and public visibility date.
- GitHub stars, forks, unique users, downloads, installations, or other usage measures.
- External contributors and merged community pull requests.
- Releases published and release cadence.
- External projects, papers, labs, or organizations relying on the project.
- A public demo URL and sanitized screenshots, if deployed.
- A working public contribution and security-reporting process.

## Draft application narrative

**Project summary**

Research AI is an independently developed research-workflow application intended to help researchers move from literature discovery and source collection to traceable evidence, research planning, and manuscript development. Its architecture combines a Next.js frontend, FastAPI backend, PostgreSQL with pgvector, document extraction, background processing, retrieval/embedding services, and research provenance components.

**My role**

I am the creator and primary maintainer of Research AI. I designed and implemented the application architecture and its backend and frontend code. I maintain the repository, develop features, fix integration and test issues, and manage the project's release preparation.

**Maintenance evidence**

The repository history contains 12 pull requests authored by my GitHub account during September–October 2026. Two were merged, six were still open, and four were closed without merging at the time of the audit. The work spans the frontend/BFF, provider infrastructure, research pipeline, security and authorization, and test/CI hardening. I will provide links to the relevant merged PRs and current maintenance activity after the public release.

**Why support would help**

The project has a broad technical surface: source ingestion, provenance, embeddings and retrieval, research planning, manuscript workflows, multi-user workspaces, and operational infrastructure. Codex support could help reduce the maintenance burden of regression testing, dependency and security updates, issue triage, code review, documentation, and release workflows.

**Usage and ecosystem importance**

This section must be completed after real public usage exists. At the time of this draft, I do not have verified public adoption metrics or independent community contributions to report.

**Requested support**

I would use the program's maintainer support for day-to-day coding and maintenance, API credits for carefully reviewed maintainer workflows, and conditional security tooling if the repository qualifies.

## Form fields to gather before submission

- Public GitHub repository URL after visibility is changed.
- ChatGPT account email requested by the form.
- GitHub username and the relevant maintainer role.
- OpenAI Organization ID if the form requires it.
- Links to the strongest merged PRs and releases.
- Public adoption/usage figures, only if actually available.
- A concise explanation of what Codex/API credits would be used for.

Do not submit this draft while the repository remains private or before the license, dependency, secret-history, and CI release gates are complete.
