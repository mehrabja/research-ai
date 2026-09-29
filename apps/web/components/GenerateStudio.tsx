"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useResearchContext } from "@/lib/research-context";
import { generateManuscript, generateManuscriptProse, getCurrentManuscript, getCurrentManuscriptProse } from "@/lib/api/manuscript";

export default function GenerateStudio() {
  const queryClient = useQueryClient();

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

  const manuscript = useQuery({ queryKey: ["manuscript-current", activeReportId], queryFn: () => getCurrentManuscript(activeReportId!), enabled: Boolean(activeReportId), staleTime: 10_000 });
  const prose = useQuery({ queryKey: ["manuscript-prose-current", activeReportId], queryFn: () => getCurrentManuscriptProse(activeReportId!), enabled: Boolean(activeReportId), staleTime: 10_000 });

  const architect = useMutation({
    mutationFn: () => generateManuscript(activeReportId!, false),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["manuscript-current", activeReportId] });
      await queryClient.invalidateQueries({ queryKey: ["manuscript-prose-current", activeReportId] });
    },
  });
  const proseGenerate = useMutation({
    mutationFn: () => {
      if (!manuscript.data) throw new Error("Generate the manuscript architecture first.");
      return generateManuscriptProse(activeReportId!, manuscript.data.version.id);
    },
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["manuscript-prose-current", activeReportId] }); },
  });

  const errors = [workspaces.error, projects.error, reports.error, manuscript.error, prose.error, architect.error, proseGenerate.error].filter(Boolean);
  const firstError = errors.find((error): error is Error => error instanceof Error);
  if (firstError) return <section className="card pad" role="alert"><h2>Generation unavailable</h2><p className="muted" style={{ marginTop: 6 }}>{firstError.message}</p></section>;

  return <div className="stack" style={{ gap: 16 }}>
    <section className="card pad">
      <div className="row"><div><div className="eyebrow">AI Studio</div><h2 style={{ marginTop: 4 }}>Generate with evidence</h2><p className="muted small" style={{ marginTop: 4 }}>Run the manuscript architecture and evidence-grounded prose pipelines against a real research report.</p></div><Link className="btn" href={contextHref("/evidence")}>Evidence</Link></div>
      <div style={{ marginTop: 14 }}><div className="grid grid-3">
          <div className="field">
            <label htmlFor="generate-workspace">Workspace</label>
            <select id="generate-workspace" className="input" value={activeWorkspaceId ?? ""} onChange={(event) => {
              setWorkspaceId(event.target.value); setProjectId(undefined); setReportId(undefined);
            }}>
              {(workspaces.data ?? []).map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="generate-project">Project</label>
            <select id="generate-project" className="input" value={activeProjectId ?? ""} onChange={(event) => {
              setProjectId(event.target.value); setReportId(undefined);
            }} disabled={projects.isPending}>
              {(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="generate-report">Research report</label>
            <select id="generate-report" className="input" value={activeReportId ?? ""} onChange={(event) => setReportId(event.target.value)} disabled={reports.isPending}>
              {(reports.data ?? []).map((report) => <option key={report.id} value={report.id}>{report.topic}</option>)}
            </select>
          </div>
        </div></div>
    </section>

    {!activeReportId && !reports.isPending && <section className="card pad empty"><div className="big">∅</div><div>No research report exists in the selected project.</div><Link className="btn" href={contextHref("/research")} style={{ marginTop: 12 }}>Open Research</Link></section>}

    {activeReportId && <section className="grid grid-2">
      <section className="card pad">
        <div className="row"><h3>Manuscript architecture</h3><span className="tag">{manuscript.data ? "Ready" : "Not generated"}</span></div>
        <p className="muted small" style={{ marginTop: 8 }}>Creates or regenerates the persisted manuscript structure.</p>
        <button className="btn primary" style={{ marginTop: 12 }} disabled={architect.isPending} onClick={() => architect.mutate()}>{architect.isPending ? "Generating…" : manuscript.data ? "Regenerate manuscript" : "Generate manuscript"}</button>
        {architect.data && <div className="meta" style={{ marginTop: 8 }}>{architect.data.status}{architect.data.section_count != null ? " · " + architect.data.section_count + " sections" : ""}</div>}
      </section>
      <section className="card pad">
        <div className="row"><h3>Manuscript prose</h3><span className="tag">{prose.data?.run.status ?? "Not generated"}</span></div>
        <p className="muted small" style={{ marginTop: 8 }}>Generates persisted prose from the selected manuscript version and evidence context.</p>
        <button className="btn primary" style={{ marginTop: 12 }} disabled={!manuscript.data || proseGenerate.isPending} onClick={() => proseGenerate.mutate()}>{proseGenerate.isPending ? "Generating…" : "Generate prose"}</button>
        {proseGenerate.data && <div className="meta" style={{ marginTop: 8 }}>{proseGenerate.data.status}{proseGenerate.data.word_count != null ? " · " + proseGenerate.data.word_count + " words" : ""}</div>}
      </section>
    </section>}

    {prose.data && <section className="card pad"><div className="row"><h3>Latest generated sections</h3><span className="tag">{prose.data.run.word_count} words</span></div><div className="list" style={{ marginTop: 12 }}>{(prose.data.sections ?? []).slice(0, 3).map((section) => <article className="list-item" key={section.id}><div className="title">{section.title}</div><p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, marginTop: 7 }}>{section.text.slice(0, 900)}{section.text.length > 900 ? "…" : ""}</p></article>)}</div></section>}
  </div>;
}
