"use client";

import Link from "next/link";
import type { Route } from "next";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import {
  searchWorkspace,
  type SearchResult,
} from "@/lib/api/search";
import { useResearchContext } from "@/lib/research-context";

type ResourceFilter = "all" | SearchResult["resource_type"];

const RESOURCE_LABELS: Record<ResourceFilter, string> = {
  all: "All resources",
  project: "Projects",
  report: "Reports",
  source: "Sources",
  file: "Files",
};

export default function GlobalSearchView() {
  const { workspaceId, workspace, contextHref } = useResearchContext();
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [resourceFilter, setResourceFilter] =
    useState<ResourceFilter>("all");

  const resultsQuery = useQuery({
    queryKey: ["global-search", workspaceId, submittedQuery],
    queryFn: () => searchWorkspace(workspaceId!, submittedQuery, 50),
    enabled: Boolean(workspaceId && submittedQuery.length >= 2),
    staleTime: 5_000,
  });

  const items = (resultsQuery.data?.items ?? []).filter(
    (item) =>
      resourceFilter === "all" ||
      item.resource_type === resourceFilter,
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = query.trim();
    if (next.length < 2) return;
    setSubmittedQuery(next);
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Workspace search</div>
            <h2 style={{ marginTop: 4 }}>Search your research data</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Searches projects, reports, saved sources, and extracted
              project files inside the active workspace.
            </p>
          </div>
          <span className="tag">
            {workspace?.name ?? "No workspace"}
          </span>
        </div>

        <form onSubmit={submit} style={{ marginTop: 14 }}>
          <div className="row" style={{ alignItems: "stretch" }}>
            <input
              className="input"
              style={{ flex: 1 }}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search projects, reports, sources, files…"
              aria-label="Workspace search query"
              minLength={2}
            />
            <button
              className="btn primary"
              type="submit"
              disabled={!workspaceId || query.trim().length < 2}
            >
              Search
            </button>
          </div>
        </form>

        <div className="row" style={{ marginTop: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="muted small">Resource type</span>
            <select
              className="input"
              value={resourceFilter}
              onChange={(event) =>
                setResourceFilter(event.target.value as ResourceFilter)
              }
              aria-label="Search resource type"
            >
              {(Object.keys(RESOURCE_LABELS) as ResourceFilter[]).map(
                (value) => (
                  <option key={value} value={value}>
                    {RESOURCE_LABELS[value]}
                  </option>
                ),
              )}
            </select>
          </label>
        </div>
      </section>

      {!workspaceId && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>Select or create a workspace before searching.</div>
          <Link
            className="btn primary"
            style={{ marginTop: 12 }}
            href={contextHref("/workspace")}
          >
            Open workspace
          </Link>
        </section>
      )}

      {resultsQuery.error instanceof Error && (
        <section className="card pad" role="alert">
          <h3>Search unavailable</h3>
          <p className="muted small" style={{ marginTop: 6 }}>
            {resultsQuery.error.message}
          </p>
        </section>
      )}

      {submittedQuery && !resultsQuery.isPending && !resultsQuery.error && (
        <section className="card pad">
          <div className="row">
            <div>
              <h3>Results</h3>
              <div className="muted small">
                {resultsQuery.data?.total ?? 0} matches for{" "}
                <strong>{submittedQuery}</strong>
              </div>
            </div>
            <span className="tag">Live API</span>
          </div>

          <div className="list" style={{ marginTop: 12 }}>
            {items.map((item) => (
              <SearchResultItem
                key={item.resource_type + ":" + item.id}
                item={item}
                href={buildResultHref(item)}
              />
            ))}

            {items.length === 0 && (
              <div className="empty">
                <div className="big">∅</div>
                <div>No matching resources.</div>
              </div>
            )}
          </div>
        </section>
      )}

      {resultsQuery.isPending && (
        <section className="card pad" aria-busy="true">
          <div className="muted">Searching workspace data…</div>
        </section>
      )}
    </div>
  );
}

function SearchResultItem({
  item,
  href,
}: {
  item: SearchResult;
  href: string;
}) {
  return (
    <Link className="list-item" href={href as Route}>
      <div className="row">
        <div style={{ minWidth: 0 }}>
          <div className="title">{item.title}</div>
          <div className="meta">
            {RESOURCE_LABELS[item.resource_type]} ·{" "}
            {new Date(item.updated_at).toLocaleString()}
          </div>
        </div>
        <span className="tag">
          {RESOURCE_LABELS[item.resource_type]}
        </span>
      </div>
      {item.snippet && (
        <div className="muted small" style={{ marginTop: 6 }}>
          {item.snippet}
        </div>
      )}
    </Link>
  );
}

function buildResultHref(item: SearchResult): string {
  switch (item.resource_type) {
    case "project":
      return "/projects/" + item.id + "?projectId=" + item.id;
    case "report":
      return (
        "/reports/" +
        item.id +
        "?projectId=" +
        item.project_id +
        "&reportId=" +
        item.id
      );
    case "source":
      return (
        "/sources?projectId=" +
        item.project_id +
        "&reportId=" +
        item.report_id
      );
    case "file":
      return "/files?projectId=" + item.project_id;
  }
}
