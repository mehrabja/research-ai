"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import {
  createResearchReport,
  saveSource,
  searchSources,
  type SourceCandidate,
} from "@/lib/api/research";
import { useResearchContext } from "@/lib/research-context";

const DEFAULT_QUERY =
  "transformer-based neural decoding of sparse fMRI under low-data conditions";

export default function ResearchDiscovery() {
  const {
    projectId,
    reportId,
    reportsQuery,
    setReport,
    contextHref,
  } = useResearchContext();

  const [query, setQuery] = useState(DEFAULT_QUERY);
  const contextKey = `${projectId ?? ""}:${reportId ?? ""}`;
  const [resultsState, setResultsState] = useState<{
    key: string;
    results: SourceCandidate[];
    savedKeys: Set<string>;
  }>({ key: "", results: [], savedKeys: new Set() });

  const results =
    resultsState.key === contextKey ? resultsState.results : [];
  const savedKeys =
    resultsState.key === contextKey
      ? resultsState.savedKeys
      : new Set<string>();

  const createReport = useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error(
          "Select a research project before creating a report.",
        );
      }
      return createResearchReport(
        query.trim(),
        projectId,
      );
    },
    onSuccess: async (report) => {
      const refreshed = await reportsQuery.refetch();
      if (
        refreshed.data?.some(
          (item) => item.id === report.id,
        )
      ) {
        setReport(report.id);
      }
    },
  });

  const discovery = useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error(
          "Select a research project before running discovery.",
        );
      }

      let activeReportId = reportId;

      if (!activeReportId) {
        const report = await createResearchReport(
          query.trim(),
          projectId,
        );
        const refreshed = await reportsQuery.refetch();
        activeReportId = report.id;
        if (
          refreshed.data?.some(
            (item) => item.id === report.id,
          )
        ) {
          setReport(report.id);
        }
      }

      return searchSources(
        activeReportId,
        query.trim(),
      );
    },
    onSuccess: (nextResults) =>
      setResultsState({
        key: contextKey,
        results: nextResults,
        savedKeys: new Set(),
      }),
  });

  const save = useMutation({
    mutationFn: (candidate: SourceCandidate) => {
      if (!reportId) {
        throw new Error(
          "Create or select a research report before saving sources.",
        );
      }
      return saveSource(reportId, candidate);
    },
    onSuccess: async (_source, candidate) => {
      setResultsState((current) => {
        const next =
          current.key === contextKey
            ? new Set(current.savedKeys)
            : new Set<string>();
        next.add(sourceKey(candidate));
        return {
          key: contextKey,
          results: current.key === contextKey ? current.results : [],
          savedKeys: next,
        };
      });
    },
  });

  const busy =
    reportsQuery.isPending ||
    discovery.isPending ||
    createReport.isPending ||
    save.isPending;

  if (!projectId) {
    return (
      <section className="card pad empty">
        <div className="big">∅</div>
        <h2>Select a research project</h2>
        <p className="muted">
          Discovery is project-scoped. Select a project from the
          context switcher above to continue.
        </p>
        <Link
          className="btn primary"
          style={{ marginTop: 14 }}
          href={contextHref("/workspace")}
        >
          Open workspace
        </Link>
      </section>
    );
  }

  const activeReportId = reportId;

  return (
    <>
      <div className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">
              Project: {projectId.slice(0, 8)}…
            </div>
            <h2>Literature discovery</h2>
            <p className="muted small">
              Federated source discovery runs inside the active
              research project and report.
            </p>
          </div>
          <span className="tag">Project scoped</span>
          {activeReportId && (
            <span className="tag success">
              Report selected
            </span>
          )}
        </div>

        <div className="field" style={{ marginTop: 14 }}>
          <label htmlFor="research-question">
            Research question
          </label>
          <input
            id="research-question"
            className="input"
            value={query}
            onChange={(event) =>
              setQuery(event.target.value)
            }
          />
        </div>

        <div className="actions" style={{ marginTop: 12 }}>
          {!activeReportId && (
            <button
              className="btn"
              type="button"
              disabled={
                busy || query.trim().length < 3
              }
              onClick={() =>
                createReport.mutate()
              }
            >
              Create research report
            </button>
          )}

          <button
            className="btn primary"
            type="button"
            disabled={
              busy || query.trim().length < 3
            }
            onClick={() =>
              discovery.mutate()
            }
          >
            {discovery.isPending
              ? "Searching…"
              : "Run discovery →"}
          </button>
        </div>

        <div className="pillbar" style={{ marginTop: 12 }}>
          <span className="tag">OpenAlex</span>
          <span className="tag">Semantic Scholar</span>
          <span className="tag">Crossref</span>
          <span className="tag success">
            Deduplication on
          </span>
        </div>
      </div>

      {(reportsQuery.error ||
        createReport.error ||
        discovery.error ||
        save.error) && (
        <div
          className="card pad"
          style={{ marginTop: 16 }}
          role="alert"
        >
          <p className="muted">
            {reportsQuery.error?.message ??
              createReport.error?.message ??
              discovery.error?.message ??
              save.error?.message}
          </p>
        </div>
      )}

      {results.length > 0 && (
        <div
          className="card pad"
          style={{ marginTop: 16 }}
        >
          <div className="row">
            <div>
              <h3>Live results</h3>
              <div className="muted small">
                {results.length} candidates from the federated
                discovery API
              </div>
            </div>
            <span className="tag success">
              Live
            </span>
          </div>

          <div className="list" style={{ marginTop: 10 }}>
            {results.map((candidate) => {
              const key = sourceKey(candidate);
              const saved = savedKeys.has(key);

              return (
                <article
                  className="list-item"
                  key={key}
                >
                  <div className="row">
                    <div style={{ minWidth: 0 }}>
                      <div className="title">
                        {candidate.title}
                      </div>
                      <div className="meta">
                        {candidate.year ??
                          "Year n/a"}{" "}
                        ·{" "}
                        {candidate.citation_count ??
                          0} citations ·{" "}
                        {candidate.source_api}
                      </div>
                    </div>

                    <button
                      className="btn ghost"
                      type="button"
                      disabled={
                        saved || save.isPending
                      }
                      onClick={() =>
                        save.mutate(candidate)
                      }
                    >
                      {saved ? "Saved" : "Save"}
                    </button>
                  </div>

                  {candidate.abstract && (
                    <p
                      className="muted small"
                      style={{ marginTop: 7 }}
                    >
                      {candidate.abstract.slice(
                        0,
                        320,
                      )}
                      {candidate.abstract.length >
                      320
                        ? "…"
                        : ""}
                    </p>
                  )}

                  <div
                    className="pillbar"
                    style={{ marginTop: 8 }}
                  >
                    {candidate.doi && (
                      <span className="tag">
                        DOI {candidate.doi}
                      </span>
                    )}
                    {candidate.source_meta
                      ?.is_open_access === true && (
                      <span className="tag success">
                        Open access
                      </span>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}

      {!discovery.isPending &&
        discovery.isSuccess &&
        results.length === 0 && (
          <div
            className="card pad empty"
            style={{ marginTop: 16 }}
          >
            <div className="big">∅</div>
            <div>No sources matched this query.</div>
          </div>
        )}
    </>
  );
}

function sourceKey(candidate: SourceCandidate): string {
  return (
    candidate.source_api +
    ":" +
    candidate.external_source_id
  );
}
