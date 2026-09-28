"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listProjectReports, listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import { getReport } from "@/lib/api/reports";
import {
  approveFinalReview,
  editFinalReview,
  getFinalReview,
  rejectFinalReview,
  requestChangesFinalReview,
} from "@/lib/api/finalReview";

const ACTION_LABELS: Record<string, string> = {
  edited: "Edited",
  approved: "Approved",
  requested_changes: "Changes requested",
  rejected: "Rejected",
};

export default function FinalReviewStudio() {
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
    queryKey: ["final-review-report", activeReportId],
    queryFn: () => getReport(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 5_000,
  });

  const review = useQuery({
    queryKey: ["final-review", activeReportId, report.data?.status],
    queryFn: () => getFinalReview(activeReportId!),
    enabled: Boolean(activeReportId && report.data?.status === "review_2"),
    staleTime: 5_000,
  });

  const reviewData = review.data;
  const draftContentForReview =
    reviewData && draftVersionId === reviewData.version_id
      ? draftContent
      : reviewData?.content ?? "";

  const invalidate = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["final-review", activeReportId],
    });
    await queryClient.invalidateQueries({
      queryKey: ["final-review-report", activeReportId],
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
      if (!currentReview) throw new Error("No final review is available.");
      if (!draftContentForReview.trim()) throw new Error("Review content cannot be empty.");
      return editFinalReview(
        activeReportId!,
        currentReview.version_id,
        draftContentForReview,
        editNotes,
      );
    },
    onSuccess: async (data) => {
      setDraftVersionId(data.version_id);
      setDraftContent(data.content);
      setEditNotes("");
      setFeedback("Final review edit saved as a new immutable report version.");
      await invalidate();
    },
  });

  const approve = useMutation({
    mutationFn: () => {
      const currentReview = review.data;
      if (!currentReview) throw new Error("No final review is available.");
      return approveFinalReview(activeReportId!, currentReview.version_id);
    },
    onSuccess: async () => {
      setDecisionNotes("");
      setFeedback("Final review approved. Report is moving to validation.");
      await invalidate();
    },
  });

  const requestChanges = useMutation({
    mutationFn: () => {
      const currentReview = review.data;
      if (!currentReview) throw new Error("No final review is available.");
      if (!decisionNotes.trim()) throw new Error("Notes are required when requesting changes.");
      return requestChangesFinalReview(
        activeReportId!,
        currentReview.version_id,
        decisionNotes,
      );
    },
    onSuccess: async () => {
      setDecisionNotes("");
      setFeedback("Final-review change request recorded in audit history.");
      await invalidate();
    },
  });

  const reject = useMutation({
    mutationFn: () => {
      const currentReview = review.data;
      if (!currentReview) throw new Error("No final review is available.");
      if (!decisionNotes.trim()) throw new Error("Notes are required when rejecting the review.");
      return rejectFinalReview(
        activeReportId!,
        currentReview.version_id,
        decisionNotes,
      );
    },
    onSuccess: async () => {
      setDecisionNotes("");
      setFeedback("Final-review rejection recorded in audit history.");
      await invalidate();
    },
  });

  const errors = [
    workspaces.error,
    projects.error,
    reports.error,
    report.error,
    review.error,
  ].filter(Boolean);
  const firstError = errors.find(
    (error): error is Error => error instanceof Error,
  );
  const actionError =
    edit.error ?? approve.error ?? requestChanges.error ?? reject.error;

  if (firstError) {
    return (
      <section className="card pad" role="alert">
        <h2>Final review unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {firstError.message}
        </p>
      </section>
    );
  }

  const status = report.data?.status;
  const reviewReady = status === "review_2" && Boolean(reviewData);
  const actionPending =
    edit.isPending ||
    approve.isPending ||
    requestChanges.isPending ||
    reject.isPending;

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Final gate · review_2</div>
            <h2 style={{ marginTop: 4 }}>Final review</h2>
            <p className="muted small" style={{ marginTop: 5 }}>
              Inspect the post-translation humanized output, preserve immutable
              version lineage, and approve the final report before validation.
            </p>
          </div>
          <Link className="btn" href="/translate">
            Translation pipeline
          </Link>
        </div>

        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="final-review-workspace">Workspace</label>
            <select
              id="final-review-workspace"
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
            <label htmlFor="final-review-project">Project</label>
            <select
              id="final-review-project"
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
            <label htmlFor="final-review-report">Research report</label>
            <select
              id="final-review-report"
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
      </section>

      {!activeReportId && !reports.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>No research report exists in the selected project.</div>
        </section>
      )}

      {report.data && !reviewReady && (
        <section className="card pad">
          <h3>Pipeline state</h3>
          <p className="muted" style={{ marginTop: 7, lineHeight: 1.7 }}>
            {status === "converging"
              ? "Post-translation humanization has completed. The backend convergence stage must finish before final review becomes active."
              : status === "review_2"
                ? "The final review context is not available yet."
                : status === "validating"
                  ? "Final review has been approved and validation is now active."
                  : "Final review is not active for this report yet."}
          </p>
        </section>
      )}

      {reviewReady && reviewData && (
        <>
          <section className="grid grid-3">
            <div className="card metric">
              <div className="label">Report status</div>
              <div className="value" style={{ fontSize: 20 }}>{status}</div>
              <div className="delta">{reviewData.language}</div>
            </div>
            <div className="card metric">
              <div className="label">Version</div>
              <div className="value">{reviewData.version_number}</div>
              <div className="delta">{reviewData.change_type ?? "review target"}</div>
            </div>
            <div className="card metric">
              <div className="label">Audit events</div>
              <div className="value">{reviewData.review_events.length}</div>
              <div className="delta">Post-translation review</div>
            </div>
          </section>

          <section className="card pad">
            <h3>Final output</h3>
            <div className="field" style={{ marginTop: 12 }}>
              <label htmlFor="final-review-content">Review content</label>
              <textarea
                id="final-review-content"
                className="input"
                rows={20}
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
              <label htmlFor="final-review-edit-notes">
                Edit notes <span className="muted">(optional)</span>
              </label>
              <textarea
                id="final-review-edit-notes"
                className="input"
                rows={3}
                maxLength={2000}
                value={editNotes}
                onChange={(event) => setEditNotes(event.target.value)}
                disabled={actionPending}
                placeholder="Explain substantive edits to the final output."
              />
            </div>

            <div className="actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn primary"
                disabled={
                  actionPending ||
                  !draftContentForReview.trim() ||
                  draftContentForReview === reviewData.content
                }
                onClick={() => edit.mutate()}
              >
                {edit.isPending ? "Saving…" : "Save review edit"}
              </button>
              <button
                type="button"
                className="btn"
                disabled={actionPending}
                onClick={() => {
                  setDraftVersionId(reviewData.version_id);
                  setDraftContent(reviewData.content);
                }}
              >
                Reset draft
              </button>
            </div>
          </section>

          <section className="card pad">
            <h3>Final decision</h3>
            <p className="muted small" style={{ marginTop: 5 }}>
              Approval advances the report to validation. Request changes and
              rejection stay in review_2 while preserving an audit record.
            </p>

            <div className="field" style={{ marginTop: 12 }}>
              <label htmlFor="final-review-decision-notes">Decision notes</label>
              <textarea
                id="final-review-decision-notes"
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
                disabled={actionPending}
                onClick={() => approve.mutate()}
              >
                {approve.isPending ? "Approving…" : "Approve for validation"}
              </button>
              <button
                type="button"
                className="btn"
                disabled={actionPending || !decisionNotes.trim()}
                onClick={() => requestChanges.mutate()}
              >
                {requestChanges.isPending ? "Recording…" : "Request changes"}
              </button>
              <button
                type="button"
                className="btn"
                disabled={actionPending || !decisionNotes.trim()}
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
                  Backend audit events for the final review gate.
                </div>
              </div>
              <span className="tag">{reviewData.review_events.length}</span>
            </div>

            {reviewData.review_events.length === 0 ? (
              <div className="empty" style={{ marginTop: 12 }}>
                <div>No final-review actions have been recorded yet.</div>
              </div>
            ) : (
              <div className="list" style={{ marginTop: 12 }}>
                {[...reviewData.review_events].reverse().map((event) => (
                  <div className="list-item" key={event.id}>
                    <div className="row">
                      <div className="strong">
                        {ACTION_LABELS[event.action] ?? event.action}
                      </div>
                      <span className="tag">{event.created_at}</span>
                    </div>
                    <div className="meta" style={{ marginTop: 5 }}>
                      User {event.user_id.slice(0, 8)}… ·{" "}
                      {event.version_id === reviewData.version_id
                        ? `version ${reviewData.version_number}`
                        : "previous version"}
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
    </div>
  );
}
