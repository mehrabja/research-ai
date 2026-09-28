"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listProjectReports, listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import {
  approvePreTranslationReview,
  editPreTranslationReview,
  getPreTranslationReview,
  rejectPreTranslationReview,
  requestChangesPreTranslationReview,
} from "@/lib/api/translation";
import { getReport } from "@/lib/api/reports";

const REVIEW_ACTION_LABELS: Record<string, string> = {
  edited: "Edited",
  approved: "Approved",
  requested_changes: "Changes requested",
  rejected: "Rejected",
};

export default function TranslationStudio() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [reportId, setReportId] = useState<string>();
  const [draftContent, setDraftContent] = useState("");
  const [draftVersionId, setDraftVersionId] = useState<string>();
  const [editNotes, setEditNotes] = useState("");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [feedback, setFeedback] = useState<string>();
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

  const report = useQuery({
    queryKey: ["report", activeReportId],
    queryFn: () => getReport(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });

  const review = useQuery({
    queryKey: ["pre-translation-review", activeReportId, report.data?.status],
    queryFn: () => getPreTranslationReview(activeReportId!),
    enabled: Boolean(
      activeReportId && report.data?.status === "pre_translation_review",
    ),
    staleTime: 5_000,
  });

  const invalidateReview = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["pre-translation-review", activeReportId],
    });
    await queryClient.invalidateQueries({
      queryKey: ["report", activeReportId],
    });
    await queryClient.invalidateQueries({
      queryKey: ["project-reports", activeProjectId],
    });
  };

  const edit = useMutation({
    mutationFn: () => {
      const currentReview = review.data;
      if (!currentReview) throw new Error("No pre-translation review is available.");
      if (!draftContentForReview.trim()) throw new Error("Review content cannot be empty.");
      return editPreTranslationReview(
        activeReportId!,
        currentReview.version_id,
        draftContentForReview,
        editNotes,
      );
    },
    onSuccess: async (data) => {
      setDraftContent(data.content);
      setEditNotes("");
      setFeedback("Review edit saved as a new immutable report version.");
      await invalidateReview();
    },
  });

  const approve = useMutation({
    mutationFn: () => {
      const currentReview = review.data;
      if (!currentReview) throw new Error("No pre-translation review is available.");
      return approvePreTranslationReview(activeReportId!, currentReview.version_id);
    },
    onSuccess: async (data) => {
      setDecisionNotes("");
      setFeedback(`Pre-translation review approved. Report state is now ${data.status}.`);
      await invalidateReview();
    },
  });

  const requestChanges = useMutation({
    mutationFn: () => {
      const currentReview = review.data;
      if (!currentReview) throw new Error("No pre-translation review is available.");
      if (!decisionNotes.trim()) throw new Error("Notes are required when requesting changes.");
      return requestChangesPreTranslationReview(
        activeReportId!,
        currentReview.version_id,
        decisionNotes,
      );
    },
    onSuccess: async () => {
      setDecisionNotes("");
      setFeedback("Change request recorded in the pre-translation review history.");
      await invalidateReview();
    },
  });

  const reject = useMutation({
    mutationFn: () => {
      const currentReview = review.data;
      if (!currentReview) throw new Error("No pre-translation review is available.");
      if (!decisionNotes.trim()) throw new Error("Notes are required when rejecting the review.");
      return rejectPreTranslationReview(
        activeReportId!,
        currentReview.version_id,
        decisionNotes,
      );
    },
    onSuccess: async () => {
      setDecisionNotes("");
      setFeedback("Review rejection recorded in the pre-translation review history.");
      await invalidateReview();
    },
  });

  const loadingErrors = [
    workspaces.error,
    projects.error,
    reports.error,
    report.error,
    review.error,
  ].filter(Boolean);
  const firstError = loadingErrors.find(
    (error): error is Error => error instanceof Error,
  );
  const actionError =
    edit.error ?? approve.error ?? requestChanges.error ?? reject.error;
  if (firstError) {
    return (
      <section className="card pad" role="alert">
        <h2>Translation unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {firstError.message}
        </p>
      </section>
    );
  }

  const status = report.data?.status;
  const reviewData = review.data;
  const draftContentForReview =
    reviewData && draftVersionId === reviewData.version_id
      ? draftContent
      : reviewData?.content ?? "";
  const reviewReady = status === "pre_translation_review" && Boolean(reviewData);
  const actionPending =
    edit.isPending ||
    approve.isPending ||
    requestChanges.isPending ||
    reject.isPending;
  const canSaveEdit =
    Boolean(review.data) &&
    Boolean(draftContentForReview.trim()) &&
    draftContentForReview !== review.data?.content;
  const canRequestDecision = Boolean(review.data) && Boolean(decisionNotes.trim());

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Translation</div>
            <h2 style={{ marginTop: 4 }}>Translate research content</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Translation starts from the backend-controlled pre-translation
              review state. The approved report version is the translation input.
            </p>
          </div>
        </div>
        <div style={{ marginTop: 14 }}>
          <div className="grid grid-3">
            <div className="field">
              <label htmlFor="translate-workspace">Workspace</label>
              <select
                id="translate-workspace"
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
              <label htmlFor="translate-project">Project</label>
              <select
                id="translate-project"
                className="input"
                value={activeProjectId ?? ""}
                onChange={(event) => {
                  setProjectId(event.target.value);
                  setReportId(undefined);
                }}
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
              <label htmlFor="translate-report">Research report</label>
              <select
                id="translate-report"
                className="input"
                value={activeReportId ?? ""}
                onChange={(event) => setReportId(event.target.value)}
                disabled={reports.isPending}
              >
                {(reports.data ?? []).map((reportItem) => (
                  <option key={reportItem.id} value={reportItem.id}>
                    {reportItem.topic}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </section>

      {!activeReportId && !reports.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>No research report exists in the selected project.</div>
        </section>
      )}

      {report.data && (
        <>
          <section className="grid grid-3">
            <div className="card metric">
              <div className="label">Report status</div>
              <div className="value" style={{ fontSize: 21 }}>
                {status}
              </div>
              <div className="delta">{report.data.output_language}</div>
            </div>

            <div className="card metric">
              <div className="label">Translation gate</div>
              <div className="value" style={{ fontSize: 21 }}>
                {reviewReady ? "Review ready" : "Waiting"}
              </div>
              <div className="delta">
                Approval is required before translation
              </div>
            </div>

            <div className="card metric">
              <div className="label">Source version</div>
              <div className="value">
                {reviewData?.version_number ?? "—"}
              </div>
              <div className="delta">Backend review version</div>
            </div>
          </section>

          {reviewReady && review.data && (
            <>
              <section className="card pad">
                <div className="row">
                  <div>
                    <h3>Pre-translation review</h3>
                    <div className="muted small">
                      v{reviewData.version_number} · {reviewData.language} ·{" "}
                      {reviewData.change_type ?? "review target"}
                    </div>
                  </div>
                  <span className="tag">{reviewData.review_stage}</span>
                </div>

                <div className="field" style={{ marginTop: 14 }}>
                  <label htmlFor="pre-translation-content">
                    Review content
                  </label>
                  <textarea
                    id="pre-translation-content"
                    className="input"
                    rows={18}
                    value={draftContentForReview}
                    onChange={(event) => {
                      setDraftVersionId(reviewData.version_id);
                      setDraftContent(event.target.value);
                    }}
                    disabled={actionPending}
                    style={{ resize: "vertical", lineHeight: 1.7 }}
                  />
                </div>

                <div className="field" style={{ marginTop: 12 }}>
                  <label htmlFor="pre-translation-edit-notes">
                    Edit notes <span className="muted">(optional)</span>
                  </label>
                  <textarea
                    id="pre-translation-edit-notes"
                    className="input"
                    rows={3}
                    maxLength={2000}
                    value={editNotes}
                    onChange={(event) => setEditNotes(event.target.value)}
                    disabled={actionPending}
                    placeholder="Record why the review text was edited."
                  />
                </div>

                <div className="actions" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={!canSaveEdit || actionPending}
                    onClick={() => edit.mutate()}
                  >
                    {edit.isPending ? "Saving…" : "Save review edit"}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={!review.data || actionPending}
                    onClick={() => {
                      setDraftVersionId(review.data?.version_id);
                      setDraftContent(reviewData.content);
                    }}
                  >
                    Reset draft
                  </button>
                </div>
              </section>

              <section className="card pad">
                <div>
                  <h3>Review decision</h3>
                  <p className="muted small" style={{ marginTop: 5 }}>
                    Approval transitions the report to translating. Request
                    changes and rejection are recorded in the backend review
                    history; the review remains the active gate until the report
                    state changes.
                  </p>
                </div>

                <div className="field" style={{ marginTop: 12 }}>
                  <label htmlFor="pre-translation-decision-notes">
                    Decision notes
                  </label>
                  <textarea
                    id="pre-translation-decision-notes"
                    className="input"
                    rows={4}
                    maxLength={2000}
                    value={decisionNotes}
                    onChange={(event) => setDecisionNotes(event.target.value)}
                    disabled={actionPending}
                    placeholder="Required for Request changes or Reject."
                  />
                </div>

                <div className="actions" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={!review.data || actionPending}
                    onClick={() => approve.mutate()}
                  >
                    {approve.isPending ? "Approving…" : "Approve and start translation"}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={!canRequestDecision || actionPending}
                    onClick={() => requestChanges.mutate()}
                  >
                    {requestChanges.isPending ? "Recording…" : "Request changes"}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={!canRequestDecision || actionPending}
                    onClick={() => reject.mutate()}
                  >
                    {reject.isPending ? "Recording…" : "Reject review"}
                  </button>
                </div>

                {actionError instanceof Error && (
                  <div className="muted" role="alert" style={{ marginTop: 10 }}>
                    {actionError.message}
                  </div>
                )}
                {feedback && (
                  <div className="muted" role="status" style={{ marginTop: 10 }}>
                    {feedback}
                  </div>
                )}
              </section>

              <section className="card pad">
                <div className="row">
                  <div>
                    <h3>Review history</h3>
                    <div className="muted small">
                      Backend audit events for this pre-translation review.
                    </div>
                  </div>
                  <span className="tag">{reviewData.review_events.length}</span>
                </div>

                {reviewData.review_events.length === 0 ? (
                  <div className="empty" style={{ marginTop: 12 }}>
                    <div>No review actions have been recorded yet.</div>
                  </div>
                ) : (
                  <div className="list" style={{ marginTop: 12 }}>
                    {[...reviewData.review_events].reverse().map((event) => (
                      <div className="list-item" key={event.id}>
                        <div className="row">
                          <div className="strong">
                            {REVIEW_ACTION_LABELS[event.action] ?? event.action}
                          </div>
                          <span className="tag">
                            {event.created_at}
                          </span>
                        </div>
                        <div className="meta" style={{ marginTop: 5 }}>
                          User {event.user_id.slice(0, 8)}… · version{" "}
                          {event.version_id === reviewData.version_id
                            ? reviewData.version_number
                            : "previous"}
                        </div>
                        {event.notes && (
                          <p
                            className="muted small"
                            style={{ marginTop: 7, whiteSpace: "pre-wrap" }}
                          >
                            {event.notes}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}

          {!reviewReady && (
            <section className="card pad">
              <h3>Translation state</h3>
              <p className="muted" style={{ marginTop: 7, lineHeight: 1.7 }}>
                {status === "translating"
                  ? "The report has entered the translating state. Translation is managed by the backend job pipeline."
                  : status === "pre_translation_review"
                    ? "The review context is not available yet."
                    : "Translation is not currently eligible. The report must reach pre-translation review and be approved first."}
              </p>
              {feedback && (
                <div className="muted" role="status" style={{ marginTop: 10 }}>
                  {feedback}
                </div>
              )}
              {actionError instanceof Error && (
                <div className="muted" role="alert" style={{ marginTop: 10 }}>
                  {actionError.message}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
