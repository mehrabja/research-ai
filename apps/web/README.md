# Research AI — Next.js frontend

A Next.js 16 port of the 21-page static HTML/CSS prototype (`research-ai-21-pages-v5.zip`),
wired to the requested stack:

- **Next.js 16.3.6** (App Router) + **React 19.2.8** + **TypeScript 5.9.2**
- **Tailwind CSS 4.1.13** — layered on top of the prototype's existing hand-rolled
  design system (see "Styling" below) rather than replacing it
- **TanStack React Query 5.87.4** for server state
- **React Hook Form 7.62.0** + **Zod 4.1.5** for validated forms
- **Vitest** for unit tests, **Playwright** for E2E
- A **BFF / API proxy** in Next.js (`app/api/[...path]/route.ts`) that forwards every
  `/api/*` request to your FastAPI backend
- A **typed API client** (`lib/api/client.ts`) built with `openapi-fetch` over types
  generated from FastAPI's own OpenAPI schema

## Getting started

```bash
npm install
cp .env.example .env.local   # point BACKEND_URL at your FastAPI instance
npm run generate:api         # generates lib/api/schema.d.ts from FastAPI's /openapi.json
npm run dev
```

## Project structure

```
app/
  layout.tsx              root layout: self-hosted fonts, QueryClientProvider, toast host
  page.tsx                landing page ("/")
  login/, signup/          auth pages — wired with RHF + Zod + a mutation
  boot/                    the prototype's animated "00-loading" boot screen
  (app)/                   the authenticated app shell (sidebar + topbar)
    layout.tsx
    dashboard/, workspace/, research/, sources/, literature/, evidence/,
    knowledge/, files/, plan/, manuscript/, generate/, humanize/,
    translate/, collaboration/, jobs/, team/, usage-billing/, settings/
  api/[...path]/route.ts   BFF proxy to FastAPI
components/
  AppShell/                Sidebar, Topbar, nav config
  ToastProvider.tsx        React port of the prototype's assets/app.js toast
lib/
  api/                     backend.ts (proxy helpers), client.ts (typed client), schema.d.ts (generated)
  validation/              Zod schemas for the auth forms
styles/
  design-system.css        the prototype's original stylesheet (lightly patched, see below)
  boot.module.css          the boot screen's styles, scoped as a CSS Module
```

Each of the 18 inner-app pages keeps the exact markup and classes from the
original prototype — only `class` → `className`, inline `style` strings →
style objects, and a few fixes (below). They're plain server components; the
interactive parts (sidebar, topbar, forms) are isolated client components.

## Styling: Tailwind + the existing design system

The prototype ships its own compact design system — CSS variables
(`--primary`, `--border`, `--radius`, …) and utility-ish classes
(`.card`, `.btn`, `.tag`, `.grid-3`, …). Rewriting ~20KB of bespoke,
already-consistent CSS into Tailwind utilities would only add risk of visual
drift for no real benefit, so it's kept as-is in `styles/design-system.css`
and imported once in `app/globals.css`. Tailwind is layered on top via
`@theme` (mapping the same color tokens, e.g. `bg-primary`, `text-muted`,
`border-border`) so **new** components — the auth forms, anything you build
next — can use either system interchangeably.

Fonts (Inter, Manrope, Source Serif 4, JetBrains Mono) are self-hosted via
`next/font/google` instead of the prototype's Google Fonts `<link>` tags —
no extra render-blocking request, no layout shift, works offline.

## Fixes made while porting

The prompt asked me to fix anything broken in the design — here's what that was:

1. **Uncontrolled-input warnings.** A handful of `<input value="...">` and
   `<textarea>...</textarea>` elements had a static value with no `onChange`
   handler, which is exactly what triggers React's "a component is changing
   an uncontrolled input" console error. Converted them to `defaultValue`.
2. **Undefined CSS variable.** The landing page's header used
   `border-bottom: 1px solid var(--line)`, but `--line` was never defined
   anywhere in the stylesheet (only `--border` was) — so the border
   silently never rendered in the original prototype. Fixed to `var(--border)`.
3. **Non-functional mobile menu.** The "☰" button just fired a demo toast
   ("Mobile menu"). It now actually opens/closes a real sidebar drawer
   (`components/AppShell/Sidebar.tsx`), including a backdrop and outside-click
   to close.
4. **`body.landing-page` / `body.landing-page`-scoped rules.** These assumed
   a static site where each page can set its own `<body class>`. Next.js's
   root layout owns a single `<body>` for every route, so the landing page
   now wraps its content in `<div className="landing-page">` and the CSS
   selectors were changed from `body.landing-page ...` to `.landing-page ...`
   (with `min-height: 100vh` added so the background still fills the
   viewport on short pages).
5. **Internal navigation used `<a href="04-dashboard.html">` style links**
   (this was a static multi-file HTML prototype). All internal links were
   rewritten to `next/link`'s `<Link>` for client-side navigation; the sidebar
   also now highlights the *actual* active route via `usePathname()` instead
   of a hardcoded `class="active"` per exported HTML file.
6. **The boot/loading screen's JS** directly mutated the DOM
   (`getElementById(...).textContent = ...`) and had ~8KB of page-global CSS
   including a second, conflicting `:root` and `body` rule set. Ported to a
   proper client component driven by `requestAnimationFrame` + React state
   (`app/boot/page.tsx`), and scoped its styles into `styles/boot.module.css`
   so they can never leak into (or be clobbered by) the rest of the app.

## The BFF proxy

`app/api/[...path]/route.ts` forwards any request under `/api/*` to
`${BACKEND_URL}/*` (method, headers, and body included, cookies forwarded so
FastAPI sees the same session the browser would). The browser and the typed
API client only ever talk to same-origin `/api/...` — the backend's real URL
is a server-only environment variable and never reaches the client bundle.

The two auth forms (`/login`, `/signup`) call this proxy through the typed
client:

```ts
const { data, error } = await api.POST("/auth/login", { body: { email, password } });
```

`lib/api/schema.d.ts` currently contains a **hand-written placeholder** for
just the two auth endpoints, matching FastAPI's usual snake_case JSON
convention — replace it with the real thing once your backend is running:

```bash
BACKEND_OPENAPI_URL=http://localhost:8000/openapi.json npm run generate:api
```

After that, every FastAPI route becomes available with full autocomplete
and type-checking through the same `api.GET(...)` / `api.POST(...)` client —
wire up the remaining 18 pages' data (dashboard metrics, sources, evidence,
jobs, etc.) the same way the auth forms are wired, using
`@tanstack/react-query`'s `useQuery`/`useMutation` around `api.*` calls.

## Testing

```bash
npm run test       # Vitest — currently covers the Zod schemas
npm run test:e2e   # Playwright — landing → signup nav, login validation, sidebar nav
```

## What's intentionally left as-is

The 18 inner pages are still populated with the prototype's static demo data
(metrics, tables, kanban cards, the knowledge graph, etc.) and non-form
buttons still fire the same `data-toast` demo message they always did
(now via a small React-based `ToastProvider` instead of `assets/app.js`).
Wiring each of those to real backend data is the natural next step once the
OpenAPI schema is generated — the pattern to follow is exactly what
`app/login/page.tsx` and `app/signup/page.tsx` already do.
