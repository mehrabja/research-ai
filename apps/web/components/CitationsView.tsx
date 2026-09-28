"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listProjectReports, listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import { getCurrentManuscript } from "@/lib/api/manuscript";
import {
  generateCitations,
  getBibliography,
  getCitationEvidenceMatrix,
  getCitationHistory,
  getCurrentCitations,
  validateCitations,
} from "@/lib/api/citations";

export default function CitationsView() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [reportId, setReportId] = useState<string>();
  const [style, setStyle] = useState<"author_year" | "numeric">("author_year");
  const queryClient = useQueryClient();

  const workspaces = useQuery({
    queryKey: ["workspaces"],
    queryFn: listWorkspaces,
    staleTime: 30_000,
  });
  const activeWorkspaceId = workspaceId ?? workspaces.data?.[0]?.id;

  const projects = useQuery({
    queryKey: ["projects", activeWorkspaceId],
    queryFn: () => {
      if (!activeWorkspaceId) throw new Error("No workspace is selected.");
      return listProjects(activeWorkspaceId);
    },
    enabled: Boolean(activeWorkspaceId),
    staleTime: 15_000,
  });
  const activeProjectId = projectId ?? projects.data?.[0]?.id;

  const reports = useQuery({
    queryKey: ["project-reports", activeProjectId],
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return listProjectReports(activeProjectId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });
  const activeReportId = reportId ?? reports.data?.[0]?.id;

  const manuscript = useQuery({
    queryKey: ["manuscript-current", activeReportId],
    queryFn: () => getCurrentManuscript(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });
  const current = useQuery({
    queryKey: ["citations-current", activeReportId],
    queryFn: () => getCurrentCitations(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });
  const matrix = useQuery({
    queryKey: ["citation-evidence-matrix", activeReportId],
    queryFn: () => getCitationEvidenceMatrix(activeReportId!),
    enabled: Boolean(activeReportId && current.data),
    staleTime: 10_000,
  });
  const bibliography = useQuery({
    queryKey: ["bibliography", activeReportId, style],
    queryFn: () => getBibliography(activeReportId!, style),
    enabled: Boolean(activeReportId && current.data),
    staleTime: 10_000,
  });
  const history = useQuery({
    queryKey: ["citation-history", activeReportId],
    queryFn: () => getCitationHistory(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 15_000,
  });

  const generate = useMutation({
    mutationFn: () => {
      if (!manuscript.data) {
        throw new Error("Generate the manuscript before generating citations.");
      }
      return generateCitations(activeReportId!, manuscript.data.version.id, style);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["citations-current", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["citation-evidence-matrix", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["bibliography", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["citation-history", activeReportId] });
    },
  });

  const validate = useMutation({
    mutationFn: () => validateCitations(activeReportId!),
  });

  const errors = [
    workspaces.error,
    projects.error,
    reports.error,
    manuscript.error,
    current.error,
    matrix.error,
    bibliography.error,
    history.error,
    generate.error,
    validate.error,
  ].filter(Boolean);
  const firstError = errors.find(
    (error): error is Error => error instanceof Error,
  );

  if (firstError) {
    return (
      <section className="card pad" role="alert">
        <h2>Citations unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>{firstError.message}</p>
        <button
          className="btn"
          style={{ marginTop: 14 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void reports.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  const run = current.data?.run;
  const claims = current.data?.claims ?? [];
  const rows = matrix.data?.rows ?? [];
  const citationLinks = rows.reduce(
    (total, row) => total + (row.citations?.length ?? 0),
    0,
  );
  const evidenceLinks = rows.reduce(
    (total, row) => total + (row.evidence?.length ?? 0),
    0,
  );

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Citation engine</div>
            <h2 style={{ marginTop: 4 }}>Citations & bibliography</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Inspect the persisted citation run, claim support, validation and bibliography for a research report.
            </p>
          </div>
          <div className="actions">
            <Link className="btn" href="/evidence">Evidence</Link>
            <select
              className="input"
              aria-label="Citation style"
              value={style}
              onChange={(event) => setStyle(event.target.value as "author_year" | "numeric")}
            >
              <option value="author_year">Author-year</option>
              <option value="numeric">Numeric</option>
            </select>
          </div>
        </div>

        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="citation-workspace">Workspace</label>
            <select
              id="citation-workspace"
              className="input"
              value={activeWorkspaceId ?? ""}
              onChange={(event) => {
                setWorkspaceId(event.target.value);
                setProjectId(undefined);
                setReportId(undefined);
              }}
            >
              {(workspaces.data ?? []).map((workspace) => (
                <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="citation-project">Project</label>
            <select
              id="citation-project"
              className="input"
              value={activeProjectId ?? ""}
              onChange={(event) => {
                setProjectId(event.target.value);
                setReportId(undefined);
              }}
              disabled={projects.isPending}
            >
              {(projects.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="citation-report">Research report</label>
            <select
              id="citation-report"
              className="input"
              value={activeReportId ?? ""}
              onChange={(event) => setReportId(event.target.value)}
              disabled={reports.isPending}
            >
              {(reports.data ?? []).map((report) => (
                <option key={report.id} value={report.id}>{report.topic.slice(0, 60)}</option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {!activeReportId && !reports.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>No research report exists for the selected project. Create one through Research first.</div>
        </section>
      )}

      {activeReportId && (
        <>
          <section className="grid grid-4">
            <div className="card metric">
              <div className="label">Claims</div>
              <div className="value">{run?.claim_count ?? claims.length}</div>
              <div className="delta">{run?.status ?? "No run"}</div>
            </div>
            <div className="card metric">
              <div className="label">Citation links</div>
              <div className="value">{run?.citation_count ?? citationLinks}</div>
              <div className="delta">Persisted claim-citation links</div>
            </div>
            <div className="card metric">
              <div className="label">Coverage</div>
              <div className="value">
                {run ? Math.round(run.coverage_score * 100) + "%" : "—"}
              </div>
              <div className="delta">Current citation run</div>
            </div>
            <div className="card metric">
              <div className="label">Unsupported</div>
              <div className="value">{run?.unsupported_count ?? 0}</div>
              <div className="delta">Claims needing review</div>
            </div>
          </section>

          {!run && !current.isPending && (
            <section className="card pad empty">
              <div className="big">∅</div>
              <div>No citation run is available for this report yet.</div>
              <button
                className="btn primary"
                style={{ marginTop: 12 }}
                disabled={!manuscript.data || generate.isPending}
                onClick={() => generate.mutate()}
              >
                {generate.isPending ? "Generating…" : "Generate citations"}
              </button>
              {!manuscript.data && !manuscript.isPending && (
                <div className="muted small" style={{ marginTop: 8 }}>
                  Generate the manuscript first.
                </div>
              )}
            </section>
          )}

          {run && (
            <>
              <section className="card pad">
                <div className="row">
                  <div>
                    <h3>Current citation run</h3>
                    <div className="muted small">
                      {run.citation_style} · M30 {run.m30_version} · {run.status}
                    </div>
                  </div>
                  <div className="actions">
                    <button className="btn" disabled={validate.isPending} onClick={() => validate.mutate()}>
                      {validate.isPending ? "Validating…" : "Validate"}
                    </button>
                    <button className="btn primary" disabled={generate.isPending || !manuscript.data} onClick={() => generate.mutate()}>
                      {generate.isPending ? "Generating…" : "Regenerate citations"}
                    </button>
                  </div>
                </div>
                <div className="pillbar" style={{ marginTop: 12 }}>
                  <span className="tag">Evidence links {evidenceLinks}</span>
                  <span className="tag">Mixed support {run.mixed_support_count}</span>
                  <span className="tag">Duplicate references {run.duplicate_reference_count}</span>
                </div>
              </section>

              <section className="card table-wrap">
                <div style={{ padding: "0 16px 12px" }}>
                  <h3>Claims and citations</h3>
                  <div className="muted small">
                    {claims.length} claims returned by the current citation run.
                  </div>
                </div>
                <table className="table">
                  <thead>
                    <tr><th>Claim</th><th>Status</th><th>Citations</th><th>Evidence</th></tr>
                  </thead>
                  <tbody>
                    {claims.map((claim) => {
                      const row = rows.find((item) => item.claim.id === claim.id);
                      return (
                        <tr key={claim.id}>
                          <td>
                            <div className="strong">{claim.claim_text}</div>
                            <div className="meta">{claim.claim_type}</div>
                          </td>
                          <td><span className="tag">{claim.status}</span></td>
                          <td>{row?.citations?.length ?? 0}</td>
                          <td>{row?.evidence?.length ?? 0}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {claims.length === 0 && (
                  <div className="empty" style={{ margin: 16 }}>
                    <div className="big">∅</div>
                    <div>No claims were returned by the current citation run.</div>
                  </div>
                )}
              </section>

              <section className="grid grid-2">
                <section className="card pad">
                  <div className="row">
                    <h3>Bibliography</h3>
                    <span className="tag">{bibliography.data?.entries.length ?? 0}</span>
                  </div>
                  <div className="list" style={{ marginTop: 12 }}>
                    {(bibliography.data?.entries ?? []).map((entry) => (
                      <div className="list-item" key={entry.citation_id}>
                        <div className="row">
                          <span className="title">{entry.label}</span>
                          <span className="tag">{entry.display_key}</span>
                        </div>
                        <div className="muted small" style={{ marginTop: 6 }}>
                          {entry.rendered}
                        </div>
                      </div>
                    ))}
                    {bibliography.data && bibliography.data.entries.length === 0 && (
                      <div className="empty">
                        <div className="big">∅</div>
                        <div>No bibliography entries are currently cited.</div>
                      </div>
                    )}
                  </div>
                  {(bibliography.data?.unresolved_identity_ids?.length ?? 0) > 0 && (
                    <div className="muted small" style={{ marginTop: 10 }}>
                      Unresolved citation identities: {bibliography.data?.unresolved_identity_ids?.length}
                    </div>
                  )}
                </section>

                <section className="card pad">
                  <h3>Run history</h3>
                  <div className="list" style={{ marginTop: 12 }}>
                    {(history.data ?? []).map((item) => (
                      <div className="list-item" key={item.id}>
                        <div className="row">
                          <span>#{item.id.slice(0, 8)}</span>
                          <span className="tag">{item.status}</span>
                        </div>
                        <div className="meta">
                          {item.citation_style} · {item.claim_count} claims · {item.citation_count} citations · {item.created_at}
                        </div>
                      </div>
                    ))}
                    {(history.data ?? []).length === 0 && (
                      <div className="muted small">No prior citation runs.</div>
                    )}
                  </div>
                </section>
              </section>
            </>
          )}
        </>
      )}

      {validate.data && (
        <section className="card pad" role="status">
          Citation validation: <b>{validate.data.validation_status}</b>
          {(validate.data.warnings?.length ?? 0) > 0 && (
            <span className="muted"> · {validate.data.warnings?.join(" · ")}</span>
          )}
        </section>
      )}
    </div>
  );
}
