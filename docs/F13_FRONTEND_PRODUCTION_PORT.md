# F13 — Frontend Production Port

Date: 2026-10-01
Branch: phase14-15-completion

## Scope

F13 closes the frontend production-port contract after the backend feature phases F02-F12.

The production frontend now exposes the research workflow as real Next.js route modules backed by the centralized API layer. F13 also requires every authenticated application route to be protected consistently at the Next.js edge proxy.

## Route surface

The current app exposes 25 protected application routes plus 8 public page modules and 2 OAuth route handlers. The Next.js production build currently reports 35 route entries, including the API catch-all and not-found entry.

- research workflow: dashboard, research, sources, literature, evidence, plan, knowledge, manuscript, generate, humanize, translate, citations and final review
- operations: files, jobs, workspace, team, collaboration and usage/billing
- account/security: settings
- supporting public routes: landing, boot, login, signup, verification, password reset and invite
- dedicated PDF workspace and research canvas surfaces (implemented as top-level route modules and explicitly covered by the same proxy matcher)

## Security boundary

All authenticated application routes are listed in `apps/web/proxy.ts` and require either the access or refresh session cookie before the request reaches the application shell.

The application shell independently verifies the authenticated session through `/api/v1/auth/me`, so edge protection and client session verification remain defense-in-depth rather than a single control.

## Acceptance coverage

`apps/web/e2e/f13-frontend-port.spec.ts` verifies:

1. every protected production route redirects an unauthenticated browser to `/login`
2. every protected production route returns HTTP 200 and remains on its intended route for an authenticated session

The existing F11/F12 and workflow E2E suites continue to cover the deeper behavior of billing, notifications, authentication, OAuth, security, research, evidence, planning and manuscript workflows.

## Verification

From `apps/web`:

    npm run typecheck
    npm run lint
    npm test
    npm run build
    npm run test:e2e
