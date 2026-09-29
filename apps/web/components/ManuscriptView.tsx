"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useResearchContext } from "@/lib/research-context";
import {
  getCurrentManuscript,
  getCurrentManuscriptProse,
  listManuscriptVersions,
  generateManuscript,
  validateManuscript,
} from "@/lib/api/manuscript";

export default function ManuscriptView() {
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
  const firstError = errors.find((error): error is Error => error instanceof Error);
  if (firstError) return <section className="card pad" role="alert"><h2>Manuscript unavailable</h2><p className="muted" style={{ marginTop: 6 }}>{firstError.message}</p></section>;

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
            <Link className="btn primary" href={contextHref("/generate")}>AI Studio</Link>
          </div>
        </div>
      </section>

      {!activeReportId && !reports.isPending && <section className="card pad empty"><div className="big">∅</div><div>No research report exists in this project yet.</div><Link className="btn" href={contextHref("/research")} style={{ marginTop: 12 }}>Open Research</Link></section>}

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

      {validate.data && <section className="card pad" role="status">Validation: <b>{validate.data.validation_status}</b>{(validate.data.warnings?.length ?? 0) > 0 && <span className="muted"> · {validate.data.warnings?.join(" · ")}</span>}</section>}
    </div>
  );
}
