# Phase 18-20 — Chaos, Final Audit, Provider Activation

Date: 2026-09-29
Branch: phase123-integration

## Phase 18
A repeatable, non-destructive recovery gate now runs the existing failure, provider fallback,
storage, and worker recovery suites. Stale worker leases and typed transient provider failures
are explicitly covered. The repository also exposes a GitHub Actions recovery workflow.

Production fault injection is intentionally not enabled by the runner. Any live chaos exercise
must target an isolated staging environment.

## Phase 19
The final audit is a cross-platform Python gate plus the shell wrapper. It checks migration
graph prerequisites, operational artifacts, repository hygiene, and frontend security audit
before release evidence is accepted.

## Phase 20
Provider activation is explicit and environment-scoped. The activation gate validates active
provider configuration without printing secrets and can perform safe read-only checks for
OpenRouter, Semantic Scholar, OpenAlex, Crossref, and NCBI.

Object storage, email, billing, detection, OAuth, DNS/domain verification, payment catalog
setup, account creation, and production secret injection remain deployment tasks because they
require provider accounts or credentials outside repository code.

## Acceptance
Code completion is represented by the repository contracts and CI workflows.
Operational closure requires staging execution with real credentials and recorded evidence.
