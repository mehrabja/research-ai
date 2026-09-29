# F12 — Security, identity and account access

Date: 2026-09-29
Branch: phase123-integration

## Scope

F12 connects the existing backend security contracts to the production-facing frontend.

### Identity and OAuth

The login page now starts Google/GitHub OAuth through the backend provider abstraction. The browser is redirected to the provider authorization URL, and the callback is handled by a same-origin Next.js route handler.

Callback handling:

- validates provider, authorization code and state
- exchanges the callback with the FastAPI OAuth contract
- stores access and refresh credentials in HttpOnly cookies
- redirects to the authenticated dashboard
- routes callback errors back to /login

The backend persists one-time OAuth state and linked provider identities.

### Two-factor authentication

Settings now reads and mutates the real TOTP contract:

- status and recovery-code count
- authenticator setup
- TOTP verification to enable
- TOTP/recovery-code verification to disable
- one-time display of generated recovery codes during setup

MFA secrets remain server-side encrypted.

### Sessions

Settings lists active refresh sessions and allows the authenticated user to revoke an individual session. The existing backend also supports logout-all semantics.

Raw refresh tokens are never rendered in the settings UI.

### Personal API tokens

Settings now supports:

- create token with optional expiry
- one-time display of the raw rai_ secret
- list token metadata
- revoke token

The backend stores token hashes rather than raw secrets and records last-use metadata.

### Security activity

A user-facing security activity projection was added at:

GET /api/v1/auth/activity

It is intentionally derived from durable account-security records:

- account creation
- email verification
- session creation/revocation
- API token creation/revocation
- OAuth account linking

Raw structured audit logs remain server-side and are not exposed as a debug feed.

### Settings

The previous synthetic settings values and toast-only controls were removed. /settings now renders live account/security state through TanStack Query and invalidates the relevant queries after mutations.

## Verification

Frontend:

    npm run typecheck
    npm run lint
    npm test
    npm run build
    npm run test:e2e

F12 E2E coverage includes:

- live settings security surface
- security endpoint availability
- API token create/revoke
- MFA setup contract
- Google/GitHub OAuth start contracts
- Google OAuth login-button flow
