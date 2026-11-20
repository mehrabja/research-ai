"use client";

import Link from "next/link";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  embedSource,
  extractSource,
  listSources,
  type SavedSource,
} from "@/lib/api/sources";
import {
  saveSource,
  searchSources,
  type SourceCandidate,
} from "@/lib/api/research";
import { useResearchContext } from "@/lib/research-context";
import { queryKeys } from "@/lib/query-keys";

function candidateKey(candidate: SourceCandidate): string {
  return candidate.source_api + ":" + candidate.external_source_id;
}

function actionLabel(status: "idle" | "pending" | "done", label: string): string {
  if (status === "pending") return "Working…";
  if (status === "done") return "Done";
  return label;
}

export default function SourcesLibrary() {
  const [filter, setFilter] = useState("");
  const [lookup, setLookup] = useState("");
  const [lookupResults, setLookupResults] = useState<SourceCandidate[]>([]);
  const [expandedSourceId, setExpandedSourceId] = useState<string>();
  const [actionMessage, setActionMessage] = useState<string>();

  const queryClient = useQueryClient();
  const {
    projectId: activeProjectId,
    reportId: activeReportId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
    reportsQuery: reports,
    contextHref,
  } = useResearchContext();

  const sources = useQuery({
    queryKey: queryKeys.sources(activeReportId),
    queryFn: () => {
      if (!activeReportId) throw new Error("No research report is selected.");
      return listSources(activeReportId);
    },
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });

  const lookupMutation = useMutation({
    mutationFn: async () => {
      if (!activeReportId) throw new Error("Create or select a research report first.");
      const q = lookup.trim();
      if (q.length < 3) throw new Error("Enter at least 3 characters.");
      return searchSources(activeReportId, q, {
        sortBy: "relevance",
        sortOrder: "desc",
      });
    },
    onSuccess: setLookupResults,
  });

  const saveMutation = useMutation({
    mutationFn: (candidate: SourceCandidate) => {
      if (!activeReportId) throw new Error("No research report is selected.");
      return saveSource(activeReportId, candidate);
    },
    onSuccess: async (_source, candidate) => {
      setLookupResults((items) =>
        items.filter((item) => candidateKey(item) !== candidateKey(candidate)),
      );
      await queryClient.invalidateQueries({
        queryKey: queryKeys.sources(activeReportId),
      });
    },
  });

  const extractMutation = useMutation({
    mutationFn: (source: SavedSource) => {
      if (!activeReportId) throw new Error("No research report is selected.");
      return extractSource(activeReportId, source.id);
    },
    onSuccess: async (result) => {
      setActionMessage(
        "Extraction completed: " +
          result.chunk_count +
          " chunks · " +
          result.status,
      );
      await queryClient.invalidateQueries({
        queryKey: queryKeys.sources(activeReportId),
      });
    },
  });

  const embedMutation = useMutation({
    mutationFn: (source: SavedSource) => {
      if (!activeReportId) throw new Error("No research report is selected.");
      return embedSource(activeReportId, source.id);
    },
    onSuccess: async (result) => {
      setActionMessage(
        "Embedding complete: " +
          result.embedded +
          " embedded · " +
          result.failed +
          " failed · " +
          result.total_chunks +
          " total chunks.",
      );
      await queryClient.invalidateQueries({
        queryKey: queryKeys.sources(activeReportId),
      });
    },
  });

  const filteredSources = useMemo(() => {
    const normalized = filter.trim().toLowerCase();
    if (!normalized) return sources.data ?? [];
    return (sources.data ?? []).filter((source) =>
      [
        source.title,
        source.doi,
        source.source_api,
        source.external_source_id,
        ...(source.authors ?? []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [filter, sources.data]);

  if (workspaces.error || projects.error || reports.error || sources.error) {
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
              Sources registered on the selected research report.
            </p>
          </div>
          <Link className="btn primary" href={contextHref("/research")}>
            Full discovery
          </Link>
        </div>

        <div className="grid grid-2" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="source-filter">Filter saved sources</label>
            <input
              id="source-filter"
              className="input"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Title, DOI, author or provider"
            />
          </div>
          <div className="field">
            <label htmlFor="source-lookup">Find by title, DOI or URL</label>
            <div className="actions">
              <input
                id="source-lookup"
                className="input"
                value={lookup}
                onChange={(event) => setLookup(event.target.value)}
                placeholder="10.xxxx/... or https://…"
                onKeyDown={(event) => {
                  if (event.key === "Enter") lookupMutation.mutate();
                }}
                disabled={!activeReportId || lookupMutation.isPending}
              />
              <button
                className="btn"
                type="button"
                onClick={() => lookupMutation.mutate()}
                disabled={
                  !activeReportId ||
                  lookup.trim().length < 3 ||
                  lookupMutation.isPending
                }
              >
                {lookupMutation.isPending ? "Searching…" : "Find"}
              </button>
            </div>
          </div>
        </div>

        {(lookupMutation.error || actionMessage) && (
          <div className="card pad" style={{ marginTop: 12 }} role={lookupMutation.error ? "alert" : "status"}>
            <p className="muted small">
              {lookupMutation.error?.message ?? actionMessage}
            </p>
          </div>
        )}

        {lookupMutation.isSuccess && lookupResults.length === 0 && (
          <div className="empty" style={{ marginTop: 12 }}>
            No external candidates matched that query.
          </div>
        )}

        {lookupResults.length > 0 && (
          <div className="list" style={{ marginTop: 12 }}>
            {lookupResults.map((candidate) => (
              <article className="list-item" key={candidateKey(candidate)}>
                <div className="row">
                  <div style={{ minWidth: 0 }}>
                    <div className="title">{candidate.title}</div>
                    <div className="meta">
                      {candidate.year ?? "Year n/a"} ·{" "}
                      {candidate.source_api} ·{" "}
                      {candidate.citation_count ?? 0} citations
                    </div>
                  </div>
                  <button
                    className="btn primary"
                    type="button"
                    disabled={saveMutation.isPending}
                    onClick={() => saveMutation.mutate(candidate)}
                  >
                    Save
                  </button>
                </div>
                <div className="pillbar" style={{ marginTop: 8 }}>
                  {candidate.doi && <span className="tag">DOI {candidate.doi}</span>}
                  {candidate.url && <span className="tag">URL</span>}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {!selectedReport && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <h2>Select a research report</h2>
          <p className="muted">
            Saved sources are report-scoped. Open Research and create or select a report.
          </p>
          <Link
            className="btn primary"
            href={contextHref("/research")}
            style={{ marginTop: 12 }}
          >
            Open research
          </Link>
        </section>
      )}

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
            {filteredSources.map((source) => {
              const expanded = expandedSourceId === source.id;
              const extracting =
                extractMutation.isPending &&
                extractMutation.variables?.id === source.id;
              const embedding =
                embedMutation.isPending &&
                embedMutation.variables?.id === source.id;

              return (
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
                    <div className="actions">
                      <button
                        className="btn ghost"
                        type="button"
                        onClick={() =>
                          setExpandedSourceId(expanded ? undefined : source.id)
                        }
                      >
                        {expanded ? "Hide details" : "Details"}
                      </button>
                      <button
                        className="btn"
                        type="button"
                        disabled={extractMutation.isPending}
                        onClick={() => extractMutation.mutate(source)}
                      >
                        {actionLabel(
                          extracting ? "pending" : extractMutation.isSuccess && extractMutation.variables?.id === source.id ? "done" : "idle",
                          "Extract",
                        )}
                      </button>
                      <button
                        className="btn"
                        type="button"
                        disabled={embedMutation.isPending}
                        onClick={() => embedMutation.mutate(source)}
                      >
                        {actionLabel(
                          embedding ? "pending" : embedMutation.isSuccess && embedMutation.variables?.id === source.id ? "done" : "idle",
                          "Embed",
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="pillbar" style={{ marginTop: 8 }}>
                    {source.doi && <span className="tag">DOI {source.doi}</span>}
                    <span className="tag success">{source.status}</span>
                    {source.url && <span className="tag">URL available</span>}
                  </div>

                  {expanded && (
                    <div className="card pad" style={{ marginTop: 10 }}>
                      {source.authors?.length ? (
                        <p className="muted small">
                          <strong>Authors:</strong> {source.authors.join(", ")}
                        </p>
                      ) : null}
                      {source.abstract && (
                        <p className="muted small" style={{ marginTop: 8 }}>
                          <strong>Abstract:</strong> {source.abstract}
                        </p>
                      )}
                      <div className="pillbar" style={{ marginTop: 8 }}>
                        <span className="tag">External ID {source.external_source_id ?? "n/a"}</span>
                        <span className="tag">Created {new Date(source.created_at).toLocaleString()}</span>
                      </div>
                      <div className="actions" style={{ marginTop: 10 }}>
                        {source.url ? (
                          <a
                            className="btn ghost"
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open source
                          </a>
                        ) : null}
                        <Link
                          className="btn ghost"
                          href={contextHref("/evidence")}
                        >
                          View evidence
                        </Link>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}

            {!sources.isPending && filteredSources.length === 0 && (
              <div className="empty">
                <div className="big">∅</div>
                <div>
                  {filter.trim()
                    ? "No saved sources match this filter."
                    : "No saved sources for this report yet."}
                </div>
                <Link
                  className="btn primary"
                  href={contextHref("/research")}
                  style={{ marginTop: 12 }}
                >
                  Discover and save sources
                </Link>
              </div>
            )}
          </div>

          {(extractMutation.error || embedMutation.error) && (
            <div className="card pad" style={{ marginTop: 12 }} role="alert">
              <p className="muted small">
                {(extractMutation.error ?? embedMutation.error)?.message}
              </p>
            </div>
          )}
        </section>
      )}

      {!projects.isPending && (projects.data?.length ?? 0) === 0 && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>Create a project in Workspace before using report sources.</div>
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
              href={contextHref("/research?projectId=" + activeProjectId)}
              style={{ marginTop: 12 }}
            >
              Start discovery
            </Link>
          </section>
        )}
    </div>
  );
}
