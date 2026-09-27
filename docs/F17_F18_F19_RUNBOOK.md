# F17–F19 Runtime Runbook

This repository contains code and scripts for the final runtime phases. They are intentionally not executed as part of implementation.

## F17 — Production smoke

Configure the real backend URL and API_KEY (or use an authenticated bearer flow), then run scripts/production_smoke.sh.
Exercise auth register/login/refresh/logout, workspace selection, project creation, upload/download, provider matrix, search, job lifecycle, and webhook ingress.
Capture request IDs and response envelopes for failures.

## F18 — Recovery / chaos

The staging environment should inject failures into provider timeout/429/5xx, worker heartbeat expiry, PostgreSQL serialization/deadlock, object-storage read/write failure, duplicate webhook delivery, and browser access-token expiry during an API request.
Validate retry classification, terminal persistence, webhook idempotency, and BFF refresh rotation.

## F19 — Final audit

Run scripts/final_audit.sh, then repeat the F17 smoke suite against the deployment candidate. Record the migration head, deployed commit, provider configuration, storage backend, billing/email mode, and backup-restore evidence before release.
