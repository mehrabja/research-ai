"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useResearchContext } from "@/lib/research-context";
import {
  downloadPublication,
  generatePublicationCompliance,
  getCurrentPublicationCompliance,
  getCurrentPublicationTarget,
  getPublicationChecklist,
  getPublicationFindings,
  listPublicationTargets,
  selectPublicationTarget,
  validatePublicationCompliance,
  type PublicationComplianceFinding,
} from "@/lib/api/publication";
import { getCurrentManuscript, getCurrentManuscriptProse } from "@/lib/api/manuscript";

const SEVERITY_ORDER = ["blocking", "error", "warning", "info"];

function displayValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function findingClass(finding: PublicationComplianceFinding): string {
  if (finding.severity === "blocking") return "tag danger";
  if (finding.severity === "error") return "tag danger";
  if (finding.severity === "warning") return "tag warn";
  return "tag";
}

export default function PublicationStudio() {
  const [targetId, setTargetId] = useState<string>();
  const [format, setFormat] = useState<"markdown" | "html" | "json" | "docx">("docx");
  const [feedback, setFeedback] = useState<string>();
  const queryClient = useQueryClient();

  const {
    reportId: activeReportId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
    reportsQuery: reports,
    contextHref,
  } = useResearchContext();

  const manuscript = useQuery({
    queryKey: ["publication-manuscript", activeReportId],
    queryFn: () => getCurrentManuscript(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });
  const prose = useQuery({
    queryKey: ["publication-prose", activeReportId],
    queryFn: () => getCurrentManuscriptProse(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });
  const targets = useQuery({
    queryKey: ["publication-targets"],
    queryFn: listPublicationTargets,
    enabled: Boolean(activeReportId),
    staleTime: 30_000,
  });
  const selection = useQuery({
    queryKey: ["publication-target-current", activeReportId],
    queryFn: () => getCurrentPublicationTarget(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });
  const compliance = useQuery({
    queryKey: ["publication-compliance-current", activeReportId],
    queryFn: () => getCurrentPublicationCompliance(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 5_000,
  });
  const findings = useQuery({
    queryKey: ["publication-findings", activeReportId],
    queryFn: () => getPublicationFindings(activeReportId!),
    enabled: Boolean(activeReportId && compliance.data),
    staleTime: 5_000,
  });
  const checklist = useQuery({
    queryKey: ["publication-checklist", activeReportId],
    queryFn: () => getPublicationChecklist(activeReportId!),
    enabled: Boolean(activeReportId && compliance.data),
    staleTime: 5_000,
  });

  const selectedTargetId =
    targetId ?? selection.data?.target_id ?? "";
  const selectedTarget = (targets.data ?? []).find((target) => target.id === selectedTargetId);
  const manuscriptVersionId = manuscript.data?.version.id;

  const selectTarget = useMutation({
    mutationFn: () => {
      if (!activeReportId || !selectedTargetId) {
        throw new Error("Select a publication target first.");
      }
      return selectPublicationTarget(activeReportId, selectedTargetId);
    },
    onSuccess: async () => {
      setFeedback("Publication target selection saved.");
      await queryClient.invalidateQueries({
        queryKey: ["publication-target-current", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["publication-compliance-current", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["publication-findings", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["publication-checklist", activeReportId],
      });
    },
  });

  const runCompliance = useMutation({
    mutationFn: () => {
      if (!activeReportId || !manuscriptVersionId || !selectedTargetId) {
        throw new Error("A report, manuscript version, and publication target are required.");
      }
      return generatePublicationCompliance(
        activeReportId,
        manuscriptVersionId,
        selectedTargetId,
      );
    },
    onSuccess: async () => {
      setFeedback("Publication compliance run completed.");
      await queryClient.invalidateQueries({
        queryKey: ["publication-compliance-current", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["publication-findings", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["publication-checklist", activeReportId],
      });
    },
  });

  const validate = useMutation({
    mutationFn: () => {
      if (!activeReportId) throw new Error("No report is selected.");
      return validatePublicationCompliance(activeReportId);
    },
    onSuccess: (data) => {
      setFeedback(
        data.validation_status === "valid"
          ? "Publication compliance validation passed."
          : "Publication compliance validation found errors.",
      );
    },
  });

  const exportArtifact = useMutation({
    mutationFn: async () => {
      if (!activeReportId) throw new Error("No report is selected.");
      await downloadPublication(activeReportId, format);
    },
    onSuccess: () => setFeedback(`Downloaded ${format.toUpperCase()} publication artifact.`),
  });

  const queryErrors = [
    workspaces.error,
    projects.error,
    reports.error,
    manuscript.error,
    prose.error,
    targets.error,
    selection.error,
    compliance.error,
    findings.error,
    checklist.error,
  ].filter(Boolean);
  const firstError = queryErrors.find((error): error is Error => error instanceof Error);
  const mutationError =
    selectTarget.error ?? runCompliance.error ?? validate.error ?? exportArtifact.error;

  if (firstError) {
    return (
      <section className="card pad" role="alert">
        <h2>Publication unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>{firstError.message}</p>
      </section>
    );
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Publication target + export</div>
            <h2 style={{ marginTop: 4 }}>Prepare for submission</h2>
            <p className="muted small" style={{ marginTop: 5 }}>
              Select a real publication target, run its persisted compliance checks, and export the current report artifact.
            </p>
          </div>
          <div className="actions">
            <Link className="btn" href={contextHref("/final-review")}>Final review</Link>
            <Link className="btn" href={contextHref("/citations")}>Citations</Link>
          </div>
        </div>

      </section>

      {!activeReportId && !reports.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>No research report exists in the selected project.</div>
          <Link className="btn" href={contextHref("/research")} style={{ marginTop: 12 }}>Open Research</Link>
        </section>
      )}

      {activeReportId && (
        <>
          <section className="card pad">
            <div className="row">
              <div>
                <h3>Publication target</h3>
                <div className="muted small">
                  Choose the venue profile whose stored rules should drive compliance.
                </div>
              </div>
              {selectedTarget && <span className="tag">{selectedTarget.profile_version}</span>}
            </div>

            {targets.data?.length === 0 && !targets.isPending ? (
              <div className="empty" style={{ marginTop: 12 }}>
                <div className="big">∅</div>
                <div>No active publication targets are configured.</div>
              </div>
            ) : (
              <>
                <div className="field" style={{ marginTop: 12 }}>
                  <label htmlFor="publication-target">Target</label>
                  <select
                    id="publication-target"
                    className="input"
                    value={selectedTargetId}
                    onChange={(event) => setTargetId(event.target.value)}
                    disabled={targets.isPending || selectTarget.isPending}
                  >
                    <option value="">Select a target</option>
                    {(targets.data ?? []).map((target) => (
                      <option key={target.id} value={target.id}>
                        {target.venue} · {target.target_code} · {target.citation_style}
                      </option>
                    ))}
                  </select>
                </div>

                {selectedTarget && (
                  <div className="grid grid-3" style={{ marginTop: 12 }}>
                    <div className="card metric">
                      <div className="label">Venue</div>
                      <div className="value" style={{ fontSize: 20 }}>{selectedTarget.venue}</div>
                      <div className="delta">{selectedTarget.venue_type}</div>
                    </div>
                    <div className="card metric">
                      <div className="label">Citation style</div>
                      <div className="value" style={{ fontSize: 20 }}>{selectedTarget.citation_style}</div>
                      <div className="delta">Profile {selectedTarget.profile_version}</div>
                    </div>
                    <div className="card metric">
                      <div className="label">Publisher</div>
                      <div className="value" style={{ fontSize: 20 }}>{selectedTarget.publisher ?? "n/a"}</div>
                      <div className="delta">{selectedTarget.active ? "Active" : "Inactive"}</div>
                    </div>
                  </div>
                )}

                <div className="actions" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={!activeReportId || !selectedTargetId || selectTarget.isPending}
                    onClick={() => selectTarget.mutate()}
                  >
                    {selectTarget.isPending ? "Saving…" : "Save publication target"}
                  </button>
                </div>
              </>
            )}
          </section>

          <section className="card pad">
            <div className="row">
              <div>
                <h3>Compliance gate</h3>
                <div className="muted small">
                  The backend stores findings, gate state, target profile version, and context hash for this report.
                </div>
              </div>
              <span className={compliance.data?.run.gate === "blocked" ? "tag danger" : "tag"}>
                {compliance.data?.run.gate ?? "Not run"}
              </span>
            </div>

            {!manuscript.data && !manuscript.isPending ? (
              <div className="empty" style={{ marginTop: 12 }}>
                <div>No manuscript version is available for this report yet.</div>
                <Link className="btn" href={contextHref("/manuscript")} style={{ marginTop: 12 }}>Open Manuscript</Link>
              </div>
            ) : (
              <div className="actions" style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="btn primary"
                  disabled={!manuscriptVersionId || !selectedTargetId || runCompliance.isPending}
                  onClick={() => runCompliance.mutate()}
                >
                  {runCompliance.isPending ? "Running…" : "Run compliance"}
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={!compliance.data || validate.isPending}
                  onClick={() => validate.mutate()}
                >
                  {validate.isPending ? "Validating…" : "Validate stored run"}
                </button>
              </div>
            )}

            {compliance.data?.run && (
              <div className="grid grid-4" style={{ marginTop: 14 }}>
                <div className="card metric">
                  <div className="label">Findings</div>
                  <div className="value">{compliance.data.run.finding_count}</div>
                  <div className="delta">{compliance.data.run.warning_count} warnings</div>
                </div>
                <div className="card metric">
                  <div className="label">Blocking</div>
                  <div className="value">{compliance.data.run.blocking_count}</div>
                  <div className="delta">Gate {compliance.data.run.gate ?? "n/a"}</div>
                </div>
                <div className="card metric">
                  <div className="label">Errors</div>
                  <div className="value">{compliance.data.run.error_count}</div>
                  <div className="delta">{compliance.data.run.info_count} info findings</div>
                </div>
                <div className="card metric">
                  <div className="label">Context</div>
                  <div className="value" style={{ fontSize: 16 }}>{compliance.data.run.context_hash.slice(0, 10)}…</div>
                  <div className="delta">Rules {compliance.data.run.rules_version}</div>
                </div>
              </div>
            )}
          </section>

          {compliance.data && (
            <>
              <section className="card pad">
                <div className="row">
                  <div>
                    <h3>Submission checklist</h3>
                    <div className="muted small">
                      Persisted checklist state from the publication rules engine.
                    </div>
                  </div>
                  <span className="tag">{checklist.data?.target_profile_version ?? "n/a"}</span>
                </div>
                {!checklist.data?.checklist_state || Object.keys(checklist.data.checklist_state).length === 0 ? (
                  <div className="empty" style={{ marginTop: 12 }}>
                    <div>No checklist items were produced for the current target.</div>
                  </div>
                ) : (
                  <div className="list" style={{ marginTop: 12 }}>
                    {Object.entries(checklist.data.checklist_state).map(([key, value]) => (
                      <div className="list-item" key={key}>
                        <div className="row">
                          <span className="strong">{key}</span>
                          <span className="tag">{displayValue(value)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="card table-wrap">
                <div className="row" style={{ padding: "0 16px 12px" }}>
                  <div>
                    <h3>Compliance findings</h3>
                    <div className="muted small">
                      Only findings returned by the persisted publication run are shown.
                    </div>
                  </div>
                  <span className="tag">{findings.data?.length ?? 0}</span>
                </div>
                {findings.data?.length ? (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Rule</th>
                        <th>Finding</th>
                        <th>Message</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...(findings.data ?? [])]
                        .sort(
                          (a, b) =>
                            SEVERITY_ORDER.indexOf(a.severity) -
                            SEVERITY_ORDER.indexOf(b.severity),
                        )
                        .map((finding) => (
                          <tr key={finding.id}>
                            <td><span className={findingClass(finding)}>{finding.severity}</span></td>
                            <td className="mono">{finding.rule_id}</td>
                            <td><div className="strong">{finding.title}</div><div className="meta">{finding.category}</div></td>
                            <td>{finding.message}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="empty"><div>No compliance findings are stored yet.</div></div>
                )}
              </section>
            </>
          )}

          <section className="card pad">
            <div className="row">
              <div>
                <h3>Export artifact</h3>
                <div className="muted small">
                  The backend selects the latest final-review version when available, otherwise the latest completed manuscript prose run.
                </div>
              </div>
              <span className="tag">{format.toUpperCase()}</span>
            </div>

            <div className="grid grid-2" style={{ marginTop: 12 }}>
              <div className="field">
                <label htmlFor="publication-format">Format</label>
                <select
                  id="publication-format"
                  className="input"
                  value={format}
                  onChange={(event) =>
                    setFormat(event.target.value as "markdown" | "html" | "json" | "docx")
                  }
                >
                  <option value="docx">DOCX</option>
                  <option value="markdown">Markdown</option>
                  <option value="html">HTML</option>
                  <option value="json">JSON</option>
                </select>
              </div>
              <div className="card pad">
                <div className="strong">Export readiness</div>
                <div className="muted small" style={{ marginTop: 5 }}>
                  {compliance.data
                    ? compliance.data.run.gate === "blocked"
                      ? "Blocked by publication compliance findings."
                      : manuscript.data || prose.data
                        ? "An exportable report state is available."
                        : "Compliance exists, but no report content is available yet."
                    : "Run publication compliance before exporting."}
                </div>
              </div>
            </div>

            <div className="actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn primary"
                disabled={
                  !activeReportId ||
                  !compliance.data ||
                  compliance.data.run.gate === "blocked" ||
                  (!manuscript.data && !prose.data) ||
                  exportArtifact.isPending
                }
                onClick={() => exportArtifact.mutate()}
              >
                {exportArtifact.isPending ? "Preparing…" : `Download ${format.toUpperCase()}`}
              </button>
            </div>

            {mutationError instanceof Error && (
              <div className="muted" role="alert" style={{ marginTop: 10 }}>{mutationError.message}</div>
            )}
            {feedback && (
              <div className="muted" role="status" style={{ marginTop: 10 }}>{feedback}</div>
            )}

            {validate.data && (
              <div className="card pad" style={{ marginTop: 12 }}>
                <div className="strong">Validation: {validate.data.validation_status}</div>
                {validate.data.validation_errors.length > 0 && (
                  <div className="muted small" style={{ marginTop: 6 }}>
                    {validate.data.validation_errors.join(" · ")}
                  </div>
                )}
                {validate.data.warnings.length > 0 && (
                  <div className="muted small" style={{ marginTop: 6 }}>
                    {validate.data.warnings.join(" · ")}
                  </div>
                )}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
