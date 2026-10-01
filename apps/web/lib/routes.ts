import type { Route } from "next";

export const ROUTES = {
  home: "/",
  login: "/login",
  signup: "/signup",
  dashboard: "/dashboard",
  workspace: "/workspace",
  search: "/search",
  research: "/research",
  sources: "/sources",
  literature: "/literature",
  evidence: "/evidence",
  knowledge: "/knowledge",
  researchCanvas: "/research-canvas",
  files: "/files",
  pdfWorkspace: "/pdf-workspace",
  plan: "/plan",
  manuscript: "/manuscript",
  aiStudio: "/generate",
  humanize: "/humanize",
  translate: "/translate",
  finalReview: "/final-review",
  publication: "/publication",
  collaboration: "/collaboration",
  jobs: "/jobs",
  team: "/team",
  usageBilling: "/usage-billing",
  settings: "/settings",
} as const satisfies Record<string, Route>;

export type AppRoute = (typeof ROUTES)[keyof typeof ROUTES];

export const PROTECTED_ROUTES: readonly AppRoute[] = [
  ROUTES.dashboard,
  ROUTES.workspace,
  ROUTES.search,
  ROUTES.research,
  ROUTES.sources,
  ROUTES.literature,
  ROUTES.evidence,
  ROUTES.knowledge,
  ROUTES.researchCanvas,
  ROUTES.files,
  ROUTES.pdfWorkspace,
  ROUTES.plan,
  ROUTES.manuscript,
  ROUTES.aiStudio,
  ROUTES.humanize,
  ROUTES.translate,
  ROUTES.finalReview,
  ROUTES.publication,
  ROUTES.collaboration,
  ROUTES.jobs,
  ROUTES.team,
  ROUTES.usageBilling,
  ROUTES.settings,
];

export function isProtectedRoute(pathname: string): boolean {
  return PROTECTED_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(route + "/"),
  );
}
