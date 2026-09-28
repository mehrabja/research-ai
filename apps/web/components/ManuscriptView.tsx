"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listProjectReports, listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import {
  getCurrentManuscript,
  getCurrentManuscriptProse,
  listManuscriptVersions,
  generateManuscript,
  validateManuscript,
} from "@/lib/api/manuscript";

export default function ManuscriptView() {
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


  const manuscript = useQuery({
    queryKey: ["manuscript-current", activeReportId],
    queryFn: () => getCurrentManuscript(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });
  const prose = useQuery({
    queryKey: ["manuscript-prose-current", activeReportId],
    queryFn: () => getCurrentManuscriptProse(activeReportId!),
    enabled: Boolean(activeReportId && manuscript.data),
    staleTime: 10_000,
  });
  const versions = useQuery({
    queryKey: ["manuscript-versions", activeReportId],
    queryFn: () => listManuscriptVersions(activeReportId!),
    enabled: Boolean(activeReportId && manuscript.data),
    staleTime: 10_000,
  });
  const generate = useMutation({
    mutationFn: () => generateManuscript(activeReportId!, false),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["manuscript-current", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["manuscript-prose-current", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["manuscript-versions", activeReportId] });
    },
  });
  const validate = useMutation({ mutationFn: () => validateManuscript(activeReportId!) });

  const errors = [workspaces.error, projects.error, reports.error, manuscript.error, prose.error, versions.error, generate.error, validate.error].filter(Boolean);
  if (errors.length) return <section className="card pad" role="alert"><h2>Manuscript unavailable</h2><p className="muted" style={{ marginTop: 6 }}>{errors[0].message}</p></section>;

  const current = manuscript.data;
  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Manuscript architect</div>
            <h2 style={{ marginTop: 4 }}>{current?.version.title ?? "Manuscript"}</h2>
            <p className="muted small" style={{ marginTop: 4 }}>Current manuscript structure and persisted prose for the selected report.</p>
          </div>
          <div className="actions">
            <button className="btn" disabled={!activeReportId || validate.isPending} onClick={() => validate.mutate()}>{validate.isPending ? "Validating…" : "Validate"}</button>
            <Link className="btn primary" href="/generate">AI Studio</Link>
          </div>
        </div>
        <div style={{ marginTop: 14 }}><div className="grid grid-3">
          <div className="field">
            <label htmlFor="manuscript-workspace">Workspace</label>
            <select id="manuscript-workspace" className="input" value={activeWorkspaceId ?? ""} onChange={(event) => {
              setWorkspaceId(event.target.value); setProjectId(undefined); setReportId(undefined);
            }}>
              {(workspaces.data ?? []).map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="manuscript-project">Project</label>
            <select id="manuscript-project" className="input" value={activeProjectId ?? ""} onChange={(event) => {
              setProjectId(event.target.value); setReportId(undefined);
            }} disabled={projects.isPending}>
              {(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="manuscript-report">Research report</label>
            <select id="manuscript-report" className="input" value={activeReportId ?? ""} onChange={(event) => setReportId(event.target.value)} disabled={reports.isPending}>
              {(reports.data ?? []).map((report) => <option key={report.id} value={report.id}>{report.topic}</option>)}
            </select>
          </div>
        </div></div>
      </section>

      {!activeReportId && !reports.isPending && <section className="card pad empty"><div className="big">∅</div><div>No research report exists in this project yet.</div><Link className="btn" href="/research" style={{ marginTop: 12 }}>Open Research</Link></section>}

      {activeReportId && !current && !manuscript.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div><div>No manuscript has been generated for this report yet.</div>
          <button className="btn primary" style={{ marginTop: 12 }} disabled={generate.isPending} onClick={() => generate.mutate()}>{generate.isPending ? "Generating…" : "Generate manuscript"}</button>
          {generate.data && <div className="muted small" style={{ marginTop: 10 }}>{generate.data.status}{generate.data.section_count != null ? " · " + generate.data.section_count + " sections" : ""}</div>}
        </section>
      )}

      {current && <>
        <section className="grid grid-3">
          <div className="card metric"><div className="label">Version</div><div className="value">{current.version.version}</div><div className="delta">{current.version.status}</div></div>
          <div className="card metric"><div className="label">Sections</div><div className="value">{current.sections.length}</div><div className="delta">{current.research_order.length} in research order</div></div>
          <div className="card metric"><div className="label">Word target</div><div className="value">{current.version.word_target}</div><div className="delta">{current.manuscript.status}</div></div>
        </section>

        <section className="card table-wrap">
          <div className="row" style={{ padding: "0 16px 12px" }}>
            <div><h3>Manuscript structure</h3><div className="muted small">Context {current.manuscript.context_hash.slice(0, 12)}…</div></div>
            <button className="btn" disabled={generate.isPending} onClick={() => generate.mutate()}>{generate.isPending ? "Regenerating…" : "Regenerate architecture"}</button>
          </div>
          <table className="table"><thead><tr><th>Section</th><th>Purpose</th><th>Budget</th><th>Status</th></tr></thead>
            <tbody>{current.sections.map((section) => <tr key={section.id}><td><div className="strong">{section.display_order}. {section.title}</div><div className="meta">{section.section_key}</div></td><td>{section.purpose ?? "n/a"}</td><td>{section.word_budget}</td><td><span className="tag">{section.status}</span></td></tr>)}</tbody>
          </table>
        </section>

        <section className="card pad">
          <div className="row"><h3>Current prose</h3><span className="tag">{prose.data?.run.word_count ?? 0} words</span></div>
          {!prose.data && !prose.isPending && <div className="empty" style={{ marginTop: 12 }}><div className="big">∅</div><div>No completed prose run exists for this manuscript yet.</div></div>}
          {(prose.data?.sections ?? []).map((section) => <article className="list-item" key={section.id} style={{ marginTop: 10 }}>
            <div className="row"><div className="title">{section.display_order}. {section.title}</div><span className="tag">{section.status}</span></div>
            <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, marginTop: 8 }}>{section.text}</p>
            <div className="meta">{section.word_count} words · {section.paragraph_count} paragraphs</div>
          </article>)}
        </section>

        <section className="card pad">
          <div className="row"><h3>Versions</h3><span className="tag">{versions.data?.length ?? 0}</span></div>
          <div className="list" style={{ marginTop: 12 }}>{(versions.data ?? []).map((version) => <div className="list-item" key={version.id}><div className="row"><span>v{version.version} · {version.title}</span><span className="tag">{version.status}</span></div><div className="meta">{version.word_target} word target · {version.created_at}</div></div>)}</div>
        </section>
      </>}

      {validate.data && <section className="card pad" role="status">Validation: <b>{validate.data.validation_status}</b>{(validate.data.warnings?.length ?? 0) > 0 && <span className="muted"> · {validate.data.warnings.join(" · ")}</span>}</section>}
    </div>
  );
}
