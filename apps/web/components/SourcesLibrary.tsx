"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { listSources } from "@/lib/api/sources";
import { useResearchContext } from "@/lib/research-context";

export default function SourcesLibrary() {
  const [filter, setFilter] = useState("");

  const {
    workspaceId: activeWorkspaceId,
    projectId: activeProjectId,
    reportId: activeReportId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
    reportsQuery: reports,
    setWorkspace: setWorkspaceId,
    setProject: setProjectId,
    setReport: setReportId,
    contextHref,
  } = useResearchContext();

  const sources = useQuery({
    queryKey: ["sources", activeReportId],
    queryFn: () => {
      if (!activeReportId) throw new Error("No research report is selected.");
      return listSources(activeReportId);
    },
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });

  const filteredSources = useMemo(() => {
    const normalized = filter.trim().toLowerCase();
    if (!normalized) return sources.data ?? [];

    return (sources.data ?? []).filter((source) =>
      [
        source.title,
        source.doi,
        source.source_api,
        ...(source.authors ?? []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [filter, sources.data]);

  if (
    workspaces.error ||
    projects.error ||
    reports.error ||
    sources.error
  ) {
    const error =
      workspaces.error?.message ??
      projects.error?.message ??
      reports.error?.message ??
      sources.error?.message ??
      "Sources could not be loaded.";

    return (
      <section className="card pad" role="alert">
        <h2>Sources unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>{error}</p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 14 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void reports.refetch();
            void sources.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  const selectedReport = reports.data?.find(
    (report) => report.id === activeReportId,
  );

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <h2>Saved sources</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Sources actually saved to a research report.
            </p>
          </div>
          <Link className="btn primary" href={contextHref("/research")}>
            Discover more
          </Link>
        </div>

        <div className="field" style={{ marginTop: 12 }}>
          <label htmlFor="source-filter">Filter sources</label>
          <input
            id="source-filter"
            className="search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Search title, DOI, author or provider…"
          />
        </div>
      </section>

      {selectedReport && (
        <section className="card pad">
          <div className="row">
            <div>
              <div className="eyebrow">Report sources</div>
              <h2 style={{ marginTop: 4 }}>{selectedReport.topic}</h2>
              <p className="muted small" style={{ marginTop: 4 }}>
                {selectedReport.status} · updated{" "}
                {new Date(selectedReport.updated_at).toLocaleString()}
              </p>
            </div>
            <span className="tag success">
              {filteredSources.length} source{filteredSources.length === 1 ? "" : "s"}
            </span>
          </div>

          <div className="list" style={{ marginTop: 12 }}>
            {filteredSources.map((source) => (
              <article className="list-item" key={source.id}>
                <div className="row">
                  <div style={{ minWidth: 0 }}>
                    <div className="title">{source.title}</div>
                    <div className="meta">
                      {source.year ?? "Year n/a"} ·{" "}
                      {source.source_api ?? "provider n/a"} ·{" "}
                      {source.citation_count ?? 0} citations
                    </div>
                  </div>
                  {source.url ? (
                    <a
                      className="btn ghost"
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open source
                    </a>
                  ) : (
                    <span className="tag">No URL</span>
                  )}
                </div>

                <div className="pillbar" style={{ marginTop: 8 }}>
                  {source.doi && <span className="tag">DOI {source.doi}</span>}
                  <span className="tag success">{source.status}</span>
                </div>
              </article>
            ))}

            {!sources.isPending && filteredSources.length === 0 && (
              <div className="empty">
                <div className="big">∅</div>
                <div>
                  {filter.trim()
                    ? "No saved sources match this filter."
                    : "No saved sources for this report yet."}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {!projects.isPending && (projects.data?.length ?? 0) === 0 && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>Create a project in Workspace before saving report sources.</div>
          <Link className="btn" href={contextHref("/workspace")} style={{ marginTop: 12 }}>
            Open workspace
          </Link>
        </section>
      )}

      {!reports.isPending &&
        activeProjectId &&
        (reports.data?.length ?? 0) === 0 && (
          <section className="card pad empty">
            <div className="big">∅</div>
            <div>No research report exists for this project yet.</div>
            <Link
              className="btn"
              href={{ pathname: "/research", query: { projectId: activeProjectId } }}
              style={{ marginTop: 12 }}
            >
              Start discovery
            </Link>
          </section>
        )}
    </div>
  );
}
