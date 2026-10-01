# F19 — Final Audit & Production Readiness

Date: 2026-10-01
Branch: phase14-15-completion

## Scope

F19 is the repository release-readiness gate after F18 recovery coverage and before external
provider activation/runtime rollout.

## Automated controls

- Required CI, smoke, chaos/recovery, provider-activation, backup/restore, and frontend-security
  artifacts are checked by `scripts/final_audit.py`.
- Tracked non-example environment files are rejected.
- Common private-key and provider credential patterns are scanned with `git grep`.
- Frontend security audit is invoked as the final sub-check.
- Regression coverage lives in `apps/api/tests/core/test_final_audit.py`.

## Current evidence

Local acceptance already recorded on this branch includes:

- backend full test suite: PASS
- Ruff: PASS
- mypy: PASS
- Phase 18 chaos/recovery suite: PASS
- frontend typecheck, lint, unit tests, build: PASS
- frontend security audit: PASS

F17 smoke helper regression coverage is implemented in
`apps/api/tests/core/test_production_smoke.py`.

F20 provider activation regression coverage is implemented in
`apps/api/tests/core/test_provider_activation.py`, including strict heuristic rejection,
Originality activation, HTTP detector configuration requirements, and fail-closed handling of
unknown detector providers.

## Runtime closure

Repository-level readiness does not prove deployment readiness.

F17/F20 still require staging or production evidence with credentials provisioned through the
environment's secret manager. F18 live staging fault injection remains deployment-specific.

Required runtime evidence includes the configured production detector, generation provider,
academic discovery access, object storage, transactional email, and billing provider where those
features are enabled.

No production secrets belong in the repository or in chat.
