"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listProjectReports, listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import {
  getEvidenceMatrix,
  type EvidenceRow,
} from "@/lib/api/evidence";
import {
  getProjectFileEvidence,
  syncProjectFileEvidence,
  type ProjectFileEvidence,
} from "@/lib/api/project-file-evidence";

export default function EvidenceMatrixView() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [reportId, setReportId] = useState<string>();
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

  const fileEvidence = useQuery({
    queryKey: ["project-file-evidence", activeProjectId],
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return getProjectFileEvidence(activeProjectId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const sync = useMutation({
    mutationFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return syncProjectFileEvidence(activeProjectId, activeReportId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["project-file-evidence", activeProjectId],
      });
      if (activeReportId) {
        await queryClient.invalidateQueries({
          queryKey: ["evidence-matrix", activeReportId],
        });
      }
    },
  });

  const matrix = useQuery({
    queryKey: ["evidence-matrix", activeReportId],
    queryFn: () => {
      if (!activeReportId) throw new Error("No research report is selected.");
      return getEvidenceMatrix(activeReportId);
    },
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });

  const errors = [
    workspaces.error,
    projects.error,
    reports.error,
    matrix.error,
    fileEvidence.error,
    sync.error,
  ].filter(Boolean);

  if (errors.length) {
    return (
      <section className="card pad" role="alert">
        <h2>Evidence unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {(errors[0] as Error).message}
        </p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 14 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void reports.refetch();
            void matrix.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  const rows = matrix.data?.rows ?? [];
  const evidenceCount = rows.reduce(
    (total, row) => total + (row.evidence?.length ?? 0),
    0,
  );
  const unsupportedCount = rows.filter(
    (row) => row.claim.status !== "supported",
  ).length;

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">RAG / evidence layer</div>
            <h2 style={{ marginTop: 4 }}>Evidence matrix</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Claims, report citations, and project-file evidence linkage.
            </p>
          </div>
        </div>

        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="evidence-workspace">Workspace</label>
            <select
              id="evidence-workspace"
              className="input"
              value={activeWorkspaceId ?? ""}
              onChange={(event) => {
                setWorkspaceId(event.target.value);
                setProjectId(undefined);
                setReportId(undefined);
              }}
            >
              {(workspaces.data ?? []).map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="evidence-project">Project</label>
            <select
              id="evidence-project"
              className="input"
              value={activeProjectId ?? ""}
              onChange={(event) => setProjectId(event.target.value)}
              disabled={projects.isPending}
            >
              {(projects.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="evidence-report">Research report</label>
            <select
              id="evidence-report"
              className="input"
              value={activeReportId ?? ""}
              onChange={(event) => setReportId(event.target.value)}
              disabled={reports.isPending}
            >
              {(reports.data ?? []).map((report) => (
                <option key={report.id} value={report.id}>
                  {report.topic.slice(0, 60)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="card pad">
        <div className="row">
          <div>
            <h3>Project files → evidence</h3>
            <p className="muted small">
              Canonical ProjectFile → Source → Chunk linkage for this project.
            </p>
          </div>
          <button
            className="btn"
            type="button"
            disabled={!activeProjectId || sync.isPending}
            onClick={() => sync.mutate()}
          >
            {sync.isPending ? "Syncing…" : "Sync ready files"}
          </button>
        </div>

        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table className="table">
            <thead>
              <tr>
                <th>File</th>
                <th>Extraction</th>
                <th>Evidence status</th>
                <th>Sources</th>
                <th>Chunks</th>
                <th>Reports</th>
              </tr>
            </thead>
            <tbody>
              {(fileEvidence.data?.items ?? []).map(
                (item: ProjectFileEvidence) => (
                  <tr key={item.file_id}>
                    <td>
                      <div className="strong">{item.filename}</div>
                      <div className="meta">{item.file_kind}</div>
                    </td>
                    <td><span className="tag">{item.extraction_status}</span></td>
                    <td><span className="tag">{item.evidence_status}</span></td>
                    <td>{item.source_count}</td>
                    <td>{item.chunk_count}</td>
                    <td>{item.report_ids.length}</td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>

        {!fileEvidence.isPending &&
          (fileEvidence.data?.items.length ?? 0) === 0 && (
            <div className="empty" style={{ marginTop: 12 }}>
              <div className="big">∅</div>
              <div>No project files are available for evidence synchronization.</div>
            </div>
          )}
      </section>

      <section className="grid grid-3">
        <div className="card metric">
          <div className="label">Claims</div>
          <div className="value">{rows.length}</div>
          <div className="delta">Current citation run</div>
        </div>
        <div className="card metric">
          <div className="label">Evidence links</div>
          <div className="value">{evidenceCount}</div>
          <div className="delta">Persisted claim-evidence links</div>
        </div>
        <div className="card metric">
          <div className="label">Needs review</div>
          <div className="value">{unsupportedCount}</div>
          <div className="delta">Based on claim status</div>
        </div>
      </section>

      {!activeReportId && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>
            No research report exists for the selected project. Create one
            through Research discovery first.
          </div>
        </section>
      )}

      {activeReportId && rows.length === 0 && !matrix.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>
            No citation run is available yet. The evidence matrix will appear
            after a citation run has produced claims.
          </div>
        </section>
      )}

      {rows.length > 0 && (
        <EvidenceRows rows={rows} />
      )}
    </div>
  );
}

function EvidenceRows({ rows }: { rows: EvidenceRow[] }) {
  return (
    <section className="card table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Claim</th>
            <th>Evidence</th>
            <th>Citations</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.claim.id}>
              <td>
                <div className="strong">{row.claim.claim_text}</div>
                <div className="meta">
                  {row.claim.claim_type} · {row.claim.status}
                </div>
              </td>
              <td>
                {(row.evidence ?? []).length}
                {row.evidence && row.evidence.length > 0 && (
                  <div className="pillbar" style={{ marginTop: 6 }}>
                    {row.evidence.slice(0, 4).map((item) => (
                      <details key={item.id} style={{ width: "100%" }}>
                        <summary style={{ cursor: "pointer" }}>
                          <span className="tag">
                            {item.support_level} ·{" "}
                            {item.relevance_score.toFixed(2)}
                          </span>
                        </summary>
                        <div className="muted tiny" style={{ marginTop: 6 }}>
                          Evidence: {item.evidence_type} · {item.evidence_id}
                        </div>
                        <div className="muted tiny" style={{ marginTop: 3 }}>
                          Source: {item.source_id ?? "none"}
                        </div>
                        <pre
                          style={{
                            whiteSpace: "pre-wrap",
                            marginTop: 6,
                            fontSize: 11,
                          }}
                        >
                          {JSON.stringify(item.provenance, null, 2)}
                        </pre>
                      </details>
                    ))}
                  </div>
                )}
              </td>
              <td>{(row.citations ?? []).length}</td>
              <td>
                <span className="tag">{row.claim.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}