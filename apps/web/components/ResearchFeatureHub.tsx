"use client";

import Link from "next/link";
import type { Route } from "next";
import { useResearchContext } from "@/lib/research-context";

type Feature = {
  title: string;
  description: string;
  href: Route;
};

const features: Feature[] = [
  {
    title: "PDF Workspace",
    description:
      "Open the persisted document workspace for review and annotation.",
    href: "/pdf-workspace",
  },
  {
    title: "Citation Manager",
    description:
      "Inspect citation runs, validation state and bibliography workflows.",
    href: "/citations",
  },
  {
    title: "Literature Review",
    description:
      "Screen papers, inspect clusters and review evidence gaps.",
    href: "/literature",
  },
  {
    title: "Knowledge Graph",
    description:
      "Explore connected research entities and their current relationships.",
    href: "/knowledge",
  },
  {
    title: "Research Canvas",
    description:
      "Open the persistent research canvas for the active project.",
    href: "/research-canvas",
  },
  {
    title: "Collaboration",
    description:
      "Open the real collaboration and review workspace.",
    href: "/collaboration",
  },
];

export default function ResearchFeatureHub() {
  const { contextHref } = useResearchContext();

  return (
    <section
      className="card pad"
      style={{ marginTop: "16px" }}
    >
      <div className="row">
        <div>
          <h3>Research capabilities</h3>
          <div className="muted small">
            Connected modules for the active research context.
          </div>
        </div>
        <span className="tag">6 modules</span>
      </div>

      <div
        className="grid grid-3"
        style={{ marginTop: "16px" }}
      >
        {features.map((feature) => (
          <article
            className="card pad"
            key={feature.title}
          >
            <h4>{feature.title}</h4>
            <p className="muted small">
              {feature.description}
            </p>
            <Link
              className="btn"
              href={contextHref(feature.href)}
            >
              Open
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
