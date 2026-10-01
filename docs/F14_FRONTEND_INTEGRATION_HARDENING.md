# Research-AI — F14 Frontend Integration Hardening

Date: 2026-10-01
Branch: phase14-15-completion

## Goal

F14 hardens the production frontend where independent pages and client-side queries meet shared authentication, tenant-scoped data, provider configuration, and durable background jobs.

Acceptance flow:

    authenticated browser
        -> BFF
        -> backend contract
        -> tenant-scoped persistence/job state
        -> deterministic loading/error/retry behavior

## Implemented

### 1. Session-scoped React Query cache isolation

The root QueryClient now tracks the authenticated user ID. A user change clears the full query cache before authenticated UI is shown, and an invalid session clears the cache before redirecting to `/login`.

This prevents workspace, report, billing, and job data cached by one account from being reused after a different account signs in.

### 2. Typed API error normalization and retry policy

`apps/web/lib/api/errors.ts` provides a shared `ApiError` carrying HTTP status, backend error code, request ID, and retryable classification.

React Query retries transient `ApiError` responses only, while preserving one compatibility retry for legacy generic errors. The job and provider-matrix clients use the normalized error contract.

### 3. Provider matrix is a real frontend integration

Settings now consumes `/api/v1/providers/matrix` and renders the backend registry's capabilities, configured preferred provider, and registered adapters.

No provider names are treated as active runtime state merely because they appear in frontend code.

### 4. Durable Job Center

`/jobs` no longer contains demo queue counts or static job rows.

The frontend reads `/api/v1/jobs`, polls every three seconds while active jobs exist, and exposes backend retry/cancel actions. Attempt counts and persisted error codes/messages come from the real job contract.

### 5. Tenant isolation acceptance

The existing backend workspace-isolation suite validates that foreign workspace reads/writes return 404. F14 adds BFF-level acceptance that a second authenticated user cannot read another user's workspace, usage, plan, or subscription.

### 6. Auth refresh acceptance

The F14 E2E suite invalidates the browser access cookie while retaining the refresh cookie and verifies that `/api/v1/auth/me` succeeds and the BFF issues a replacement access cookie.

## Verification

From `apps/web`:

    npm run typecheck
    npm run lint
    npm test
    npm run build
    npm run test:e2e

F14 E2E coverage includes access-token refresh, provider matrix contract, workspace tenant isolation, and durable Job Center integration.

F13 route-surface tests remain separate and continue to validate the full protected frontend route contract.