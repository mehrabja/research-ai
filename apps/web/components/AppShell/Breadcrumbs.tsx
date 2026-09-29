"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useResearchContext } from "@/lib/research-context";

const labels: Record<string, string> = {
  "/dashboard": "Dashboard", "/workspace": "Workspace", "/research": "Research discovery",
  "/sources": "Sources", "/literature": "Literature", "/evidence": "Evidence",
  "/knowledge": "Knowledge graph", "/research-canvas": "Research canvas", "/files": "Files & intelligence",
  "/pdf-workspace": "PDF workspace", "/plan": "Research plan", "/manuscript": "Manuscript",
  "/generate": "AI Studio", "/humanize": "Humanize", "/translate": "Translate",
  "/final-review": "Final review", "/publication": "Publication & export", "/collaboration": "Collaboration",
  "/jobs": "Jobs", "/team": "Team", "/usage-billing": "Usage & billing", "/settings": "Settings",
};

export function Breadcrumbs() {
  const pathname = usePathname();
  const { project, contextHref } = useResearchContext();
  const label = labels[pathname] ?? Object.entries(labels).find(([prefix]) => pathname === prefix || pathname.startsWith(prefix + "/"))?.[1] ?? "Workspace";
  const showProject = Boolean(project) && !["/dashboard", "/workspace", "/settings"].includes(pathname);

  return <nav className="breadcrumbs" aria-label="Breadcrumb">
    <Link href={contextHref("/dashboard")}>Dashboard</Link>
    {showProject && <><span aria-hidden="true">/</span><span className="breadcrumb-project">{project?.name}</span></>}
    <span aria-hidden="true">/</span><span aria-current="page">{label}</span>
  </nav>;
}
