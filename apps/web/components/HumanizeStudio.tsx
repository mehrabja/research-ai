"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listProjectReports, listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import { getCurrentManuscript } from "@/lib/api/manuscript";
import { generateManuscriptHumanization, getCurrentManuscriptHumanization, validateManuscriptHumanization } from "@/lib/api/humanization";

const MODES = ["conservative", "academic", "natural_academic", "journal_targeted"];

export default function HumanizeStudio() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [reportId, setReportId] = useState<string>();
  const [mode, setMode] = useState("academic");
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


  const manuscript = useQuery({ queryKey: ["manuscript-current", activeReportId], queryFn: () => getCurrentManuscript(activeReportId!), enabled: Boolean(activeReportId), staleTime: 10_000 });
  const humanization = useQuery({ queryKey: ["humanization-current", activeReportId], queryFn: () => getCurrentManuscriptHumanization(activeReportId!), enabled: Boolean(activeReportId), staleTime: 10_000 });

  const generate = useMutation({
    mutationFn: () => {
      if (!manuscript.data) throw new Error("A manuscript version is required.");
      return generateManuscriptHumanization(activeReportId!, manuscript.data.version.id, mode);
    },
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["humanization-current", activeReportId] }); },
  });
  const validate = useMutation({ mutationFn: () => validateManuscriptHumanization(activeReportId!) });

  const errors = [workspaces.error, projects.error, reports.error, manuscript.error, humanization.error, generate.error, validate.error].filter(Boolean);
  const firstError = errors.find((error): error is Error => error instanceof Error);
  if (firstError) return <section className="card pad" role="alert"><h2>Humanization unavailable</h2><p className="muted" style={{ marginTop: 6 }}>{firstError.message}</p></section>;

  const run = humanization.data?.run;
  const preservation = run?.preservation_summary ?? {};
  return <div className="stack" style={{ gap: 16 }}>
    <section className="card pad">
      <div className="row"><div><div className="eyebrow">Language studio</div><h2 style={{ marginTop: 4 }}>Humanize manuscript</h2><p className="muted small" style={{ marginTop: 4 }}>Run the persisted M32 humanization pipeline against a selected manuscript version.</p></div>
      <button className="btn" disabled={!run || validate.isPending} onClick={() => validate.mutate()}>{validate.isPending ? "Validating…" : "Validate"}</button></div>
      <div style={{ marginTop: 14 }}><div className="grid grid-3">
          <div className="field">
            <label htmlFor="humanize-workspace">Workspace</label>
            <select id="humanize-workspace" className="input" value={activeWorkspaceId ?? ""} onChange={(event) => {
              setWorkspaceId(event.target.value); setProjectId(undefined); setReportId(undefined);
            }}>
              {(workspaces.data ?? []).map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="humanize-project">Project</label>
            <select id="humanize-project" className="input" value={activeProjectId ?? ""} onChange={(event) => {
              setProjectId(event.target.value); setReportId(undefined);
            }} disabled={projects.isPending}>
              {(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="humanize-report">Research report</label>
            <select id="humanize-report" className="input" value={activeReportId ?? ""} onChange={(event) => setReportId(event.target.value)} disabled={reports.isPending}>
              {(reports.data ?? []).map((report) => <option key={report.id} value={report.id}>{report.topic}</option>)}
            </select>
          </div>
        </div></div>
    </section>

    {!activeReportId && !reports.isPending && <section className="card pad empty"><div className="big">∅</div><div>No research report exists in the selected project.</div></section>}
    {activeReportId && !manuscript.data && !manuscript.isPending && <section className="card pad empty"><div className="big">∅</div><div>Generate the manuscript before running humanization.</div></section>}

    {manuscript.data && <>
      <section className="card pad">
        <div className="row"><div><h3>Rewrite controls</h3><div className="muted small">Mode is enforced by the M32 backend policy.</div></div>
          <select className="input" style={{ maxWidth: 220 }} value={mode} aria-label="Humanization mode" onChange={(event) => setMode(event.target.value)}>{MODES.map((item) => <option key={item} value={item}>{item}</option>)}</select>
        </div>
        <button className="btn primary" style={{ marginTop: 14 }} disabled={generate.isPending} onClick={() => generate.mutate()}>{generate.isPending ? "Rewriting…" : run ? "Run again" : "Humanize"}</button>
        {generate.data && <div className="meta" style={{ marginTop: 8 }}>{generate.data.status}{generate.data.gate ? " · gate " + generate.data.gate : ""}</div>}
      </section>

      {!run && !humanization.isPending && <section className="card pad empty"><div className="big">∅</div><div>No completed humanization run exists for this manuscript yet.</div></section>}
      {run && <>
        <section className="grid grid-3">
          <div className="card metric"><div className="label">Status</div><div className="value" style={{ fontSize: 22 }}>{run.status}</div><div className="delta">Gate {run.gate ?? "n/a"}</div></div>
          <div className="card metric"><div className="label">Mode</div><div className="value" style={{ fontSize: 22 }}>{run.mode ?? "n/a"}</div><div className="delta">{run.language}</div></div>
          <div className="card metric"><div className="label">Iterations</div><div className="value">{String(preservation.iterations ?? 0)}</div><div className="delta">Preservation {preservation.preservation_ratio != null ? Math.round(Number(preservation.preservation_ratio) * 100) + "%" : "n/a"}</div></div>
        </section>
        <section className="card pad"><h3>Preservation summary</h3><pre style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>{JSON.stringify(preservation, null, 2)}</pre></section>
      </>}
    </>}
    {validate.data && <section className="card pad" role="status">Validation: <b>{validate.data.validation_status}</b>{validate.data.gate ? " · gate " + validate.data.gate : ""}</section>}
  </div>;
}
