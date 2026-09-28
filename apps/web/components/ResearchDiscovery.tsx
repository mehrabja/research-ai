"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  createResearchReport,
  listReports,
  saveSource,
  searchSources,
  type SourceCandidate,
} from "@/lib/api/research";
import { listProjectReports } from "@/lib/api/projects";

const DEFAULT_QUERY =
  "transformer-based neural decoding of sparse fMRI under low-data conditions";

export default function ResearchDiscovery() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId") ?? undefined;
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [reportId, setReportId] = useState<string>();
  const [results, setResults] = useState<SourceCandidate[]>([]);
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());

  const reports = useQuery({
    queryKey: ["reports", projectId],
    queryFn: () => projectId ? listProjectReports(projectId) : listReports(),
    staleTime: 30_000,
  });

  const createReport = useMutation({
    mutationFn: () => createResearchReport(query.trim(), projectId),
    onSuccess: async (report) => {
      setReportId(report.id);
      await reports.refetch();
    },
  });

  const discovery = useMutation({
    mutationFn: async () => {
      let activeReportId = reportId ?? reports.data?.[0]?.id;

      if (!activeReportId) {
        const report = await createResearchReport(query.trim(), projectId);
        activeReportId = report.id;
        setReportId(activeReportId);
        await reports.refetch();
      }

      return searchSources(activeReportId, query.trim());
    },
    onSuccess: setResults,
  });

  const save = useMutation({
    mutationFn: (candidate: SourceCandidate) => {
      const activeReportId = reportId ?? reports.data?.[0]?.id;
      if (!activeReportId) {
        throw new Error("Create a research report before saving sources.");
      }
      return saveSource(activeReportId, candidate);
    },
    onSuccess: async (_source, candidate) => {
      setSavedKeys((current) => {
        const next = new Set(current);
        next.add(sourceKey(candidate));
        return next;
      });
    },
  });

  const activeReportId = reportId ?? reports.data?.[0]?.id;
  const busy =
    reports.isPending ||
    discovery.isPending ||
    createReport.isPending ||
    save.isPending;

  return (
    <>
      <div className="card pad">
        <div className="field">
          <label htmlFor="research-question">Research question</label>
          <input
            id="research-question"
            className="input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="actions" style={{ marginTop: 12 }}>
          {!activeReportId && (
            <button
              className="btn"
              type="button"
              disabled={busy || query.trim().length < 3}
              onClick={() => createReport.mutate()}
            >
              Create research report
            </button>
          )}
          <button
            className="btn primary"
            type="button"
            disabled={busy || query.trim().length < 3}
            onClick={() => discovery.mutate()}
          >
            {discovery.isPending ? "Searching…" : "Run discovery →"}
          </button>
        </div>

        <div className="pillbar" style={{ marginTop: 12 }}>
          <span className="tag">OpenAlex</span>
          <span className="tag">Semantic Scholar</span>
          <span className="tag">Crossref</span>
          <span className="tag success">Deduplication on</span>
          {projectId && <span className="tag">Project scoped</span>}
        </div>
      </div>

      {(reports.error ||
        createReport.error ||
        discovery.error ||
        save.error) && (
        <div className="card pad" style={{ marginTop: 16 }} role="alert">
          <p className="muted">
            {reports.error?.message ??
              createReport.error?.message ??
              discovery.error?.message ??
              save.error?.message}
          </p>
        </div>
      )}

      {results.length > 0 && (
        <div className="card pad" style={{ marginTop: 16 }}>
          <div className="row">
            <div>
              <h3>Live results</h3>
              <div className="muted small">
                {results.length} candidates from the federated discovery API
              </div>
            </div>
            <span className="tag success">Live</span>
          </div>

          <div className="list" style={{ marginTop: 10 }}>
            {results.map((candidate) => {
              const key = sourceKey(candidate);
              const saved = savedKeys.has(key);

              return (
                <article className="list-item" key={key}>
                  <div className="row">
                    <div style={{ minWidth: 0 }}>
                      <div className="title">{candidate.title}</div>
                      <div className="meta">
                        {candidate.year ?? "Year n/a"} ·{" "}
                        {candidate.citation_count ?? 0} citations ·{" "}
                        {candidate.source_api}
                      </div>
                    </div>
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={saved || save.isPending}
                      onClick={() => save.mutate(candidate)}
                    >
                      {saved ? "Saved" : "Save"}
                    </button>
                  </div>

                  {candidate.abstract && (
                    <p className="muted small" style={{ marginTop: 7 }}>
                      {candidate.abstract.slice(0, 320)}
                      {candidate.abstract.length > 320 ? "…" : ""}
                    </p>
                  )}

                  <div className="pillbar" style={{ marginTop: 8 }}>
                    {candidate.doi && (
                      <span className="tag">DOI {candidate.doi}</span>
                    )}
                    {candidate.source_meta?.is_open_access === true && (
                      <span className="tag success">Open access</span>
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
          <div className="card pad empty" style={{ marginTop: 16 }}>
            <div className="big">∅</div>
            <div>No sources matched this query.</div>
          </div>
        )}
    </>
  );
}

function sourceKey(candidate: SourceCandidate): string {
  return candidate.source_api + ":" + candidate.external_source_id;
}
