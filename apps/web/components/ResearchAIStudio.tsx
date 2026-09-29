"use client";

import Link from "next/link";
import type { Route } from "next";
import { useResearchContext } from "@/lib/research-context";

const modules: Array<{
  title: string;
  desc: string;
  href: Route;
}> = [
  {
    title: "PDF Workspace",
    desc: "Review documents, annotations and persisted PDF research context.",
    href: "/pdf-workspace",
  },
  {
    title: "Literature Review",
    desc: "Screen papers, inspect clusters and identify evidence gaps.",
    href: "/literature",
  },
  {
    title: "Citation Lab",
    desc: "Inspect citation runs, claim support, validation and bibliography.",
    href: "/citations",
  },
  {
    title: "Knowledge Graph",
    desc: "Explore concepts, papers and evidence relationships.",
    href: "/knowledge",
  },
  {
    title: "Research Canvas",
    desc: "Work with persisted research notes and connected context.",
    href: "/research-canvas",
  },
  {
    title: "Team Research",
    desc: "Open collaborative review, comments and team workflows.",
    href: "/collaboration",
  },
];

export default function ResearchAIStudio() {
  const { contextHref } = useResearchContext();

  return (
    <section
      className="card pad"
      style={{ marginTop: 16 }}
    >
      <div className="row">
        <div>
          <h2>Research AI Studio</h2>
          <p className="muted small">
            Connected research experiences available in the active
            context.
          </p>
        </div>
        <span className="tag">6 modules</span>
      </div>

      <div
        className="grid grid-3"
        style={{ marginTop: 16 }}
      >
        {modules.map((module) => (
          <article
            className="card pad"
            key={module.title}
          >
            <h3>{module.title}</h3>
            <p className="muted small">
              {module.desc}
            </p>
            <Link
              className="btn primary"
              href={contextHref(module.href)}
            >
              Launch
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
