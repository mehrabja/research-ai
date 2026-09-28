"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listProjectReports, listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import { getPreTranslationReview, approvePreTranslationReview } from "@/lib/api/translation";
import { getReport } from "@/lib/api/reports";

export default function TranslationStudio() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [reportId, setReportId] = useState<string>();
  const queryClient = useQueryClient();


  const workspaces = useQuery({ queryKey: ["workspaces"], queryFn: listWorkspaces, staleTime: 30_000 });
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


  const report = useQuery({ queryKey: ["report", activeReportId], queryFn: () => getReport(activeReportId!), enabled: Boolean(activeReportId), staleTime: 10_000 });
  const review = useQuery({
    queryKey: ["pre-translation-review", activeReportId, report.data?.status],
    queryFn: () => getPreTranslationReview(activeReportId!),
    enabled: Boolean(activeReportId && report.data?.status === "pre_translation_review"),
    staleTime: 5_000,
  });
  const approve = useMutation({
    mutationFn: () => {
      if (!review.data) throw new Error("No pre-translation review is available.");
      return approvePreTranslationReview(activeReportId!, review.data.version_id);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["pre-translation-review", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["project-reports", activeProjectId] });
    },
  });

  const errors = [workspaces.error, projects.error, reports.error, report.error, review.error, approve.error].filter(Boolean);
  const firstError = errors.find((error): error is Error => error instanceof Error);
  if (firstError) return <section className="card pad" role="alert"><h2>Translation unavailable</h2><p className="muted" style={{ marginTop: 6 }}>{firstError.message}</p></section>;

  const status = report.data?.status;
  const reviewReady = status === "pre_translation_review" && Boolean(review.data);
  return <div className="stack" style={{ gap: 16 }}>
    <section className="card pad"><div className="row"><div><div className="eyebrow">Translation</div><h2 style={{ marginTop: 4 }}>Translate research content</h2><p className="muted small" style={{ marginTop: 4 }}>Translation starts from the backend-controlled pre-translation review state. The approved report version is the translation input.</p></div></div><div style={{ marginTop: 14 }}><div className="grid grid-3">
          <div className="field">
            <label htmlFor="translate-workspace">Workspace</label>
            <select id="translate-workspace" className="input" value={activeWorkspaceId ?? ""} onChange={(event) => {
              setWorkspaceId(event.target.value); setProjectId(undefined); setReportId(undefined);
            }}>
              {(workspaces.data ?? []).map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="translate-project">Project</label>
            <select id="translate-project" className="input" value={activeProjectId ?? ""} onChange={(event) => {
              setProjectId(event.target.value); setReportId(undefined);
            }} disabled={projects.isPending}>
              {(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="translate-report">Research report</label>
            <select id="translate-report" className="input" value={activeReportId ?? ""} onChange={(event) => setReportId(event.target.value)} disabled={reports.isPending}>
              {(reports.data ?? []).map((report) => <option key={report.id} value={report.id}>{report.topic}</option>)}
            </select>
          </div>
        </div></div></section>

    {!activeReportId && !reports.isPending && <section className="card pad empty"><div className="big">∅</div><div>No research report exists in the selected project.</div></section>}
    {report.data && <>
      <section className="grid grid-3">
        <div className="card metric"><div className="label">Report status</div><div className="value" style={{ fontSize: 21 }}>{status}</div><div className="delta">{report.data.output_language}</div></div>
        <div className="card metric"><div className="label">Translation gate</div><div className="value" style={{ fontSize: 21 }}>{reviewReady ? "Review ready" : "Waiting"}</div><div className="delta">Approval is required before translation</div></div>
        <div className="card metric"><div className="label">Source version</div><div className="value">{review.data?.version_number ?? "—"}</div><div className="delta">Backend review version</div></div>
      </section>

      {reviewReady && review.data && <section className="card pad"><div className="row"><div><h3>Pre-translation review</h3><div className="muted small">v{review.data.version_number} · {review.data.language} · {review.data.change_type ?? "review target"}</div></div><button className="btn primary" disabled={approve.isPending} onClick={() => approve.mutate()}>{approve.isPending ? "Approving…" : "Approve and start translation"}</button></div><div className="quote-card" style={{ marginTop: 12 }}><p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, margin: 0 }}>{review.data.content}</p></div></section>}

      {!reviewReady && <section className="card pad"><h3>Translation state</h3><p className="muted" style={{ marginTop: 7, lineHeight: 1.7 }}>{status === "translating" ? "The report has entered the translating state. Translation is managed by the backend job pipeline." : status === "pre_translation_review" ? "The review context is not available yet." : "Translation is not currently eligible. The report must reach pre-translation review and be approved first."}</p></section>}
    </>}
    {approve.data && <section className="card pad" role="status">Approval recorded. Report state is now <b>{approve.data.status}</b>.</section>}
  </div>;
}
