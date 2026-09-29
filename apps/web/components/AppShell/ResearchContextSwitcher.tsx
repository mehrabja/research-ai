"use client";

import { useResearchContext } from "@/lib/research-context";

export function ResearchContextSwitcher() {
  const { workspaceId, projectId, reportId, workspacesQuery, projectsQuery, reportsQuery, setWorkspace, setProject, setReport, invalid, resetContext } = useResearchContext();

  if (invalid) return <div className="context-switcher" role="alert"><span className="tag danger">Context unavailable</span><button className="btn ghost" type="button" onClick={resetContext}>Reset</button></div>;

  return <div className="context-switcher" aria-label="Research context">
    <label className="sr-only" htmlFor="global-workspace">Workspace</label>
    <select id="global-workspace" className="context-select" value={workspaceId ?? ""} onChange={(e) => setWorkspace(e.target.value)} disabled={workspacesQuery.isPending || (workspacesQuery.data?.length ?? 0) === 0} title="Workspace">
      {(workspacesQuery.data ?? []).length === 0 ? <option value="">No workspace</option> : (workspacesQuery.data ?? []).map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
    </select>
    <label className="sr-only" htmlFor="global-project">Project</label>
    <select id="global-project" className="context-select context-project" value={projectId ?? ""} onChange={(e) => setProject(e.target.value)} disabled={projectsQuery.isPending || (projectsQuery.data?.length ?? 0) === 0} title="Project">
      {(projectsQuery.data ?? []).length === 0 ? <option value="">No project</option> : (projectsQuery.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
    </select>
    <label className="sr-only" htmlFor="global-report">Research report</label>
    <select id="global-report" className="context-select context-report" value={reportId ?? ""} onChange={(e) => setReport(e.target.value)} disabled={reportsQuery.isPending || (reportsQuery.data?.length ?? 0) === 0} title="Research report">
      {(reportsQuery.data ?? []).length === 0 ? <option value="">No report</option> : (reportsQuery.data ?? []).map((report) => <option key={report.id} value={report.id}>{report.topic.slice(0, 48)}</option>)}
    </select>
  </div>;
}
