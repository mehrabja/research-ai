"use client";

import {
  useEffect,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function HumanReviewPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [reportId, setReportId] = useState("");
  const [content, setContent] = useState("");
  const [notes, setNotes] = useState("");

  const reports = useQuery({
    queryKey: ["reports", workspaceId],
    queryFn: () => api.reports(workspaceId!),
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (!reportId && reports.data?.[0]?.id) {
      setReportId(reports.data[0].id);
    }
  }, [reports.data, reportId]);

  const review = useQuery({
    queryKey: ["pre-translation-review", reportId],
    queryFn: () =>
      api.preTranslationReview(reportId),
    enabled: !!reportId,
    retry: false,
  });

  useEffect(() => {
    if (!review.data) {
      return;
    }

    setContent(review.data.content);
    setNotes("");
  }, [review.data]);

  const refresh = () => {
    queryClient.invalidateQueries({
      queryKey: [
        "pre-translation-review",
        reportId,
      ],
    });
  };

  const edit = useMutation({
    mutationFn: () =>
      api.editPreTranslationReview(
        reportId,
        {
          version_id:
            review.data!.version_id,
          content,
          notes:
            notes.trim() || null,
        },
      ),
    onSuccess: refresh,
  });

  const approve = useMutation({
    mutationFn: () =>
      api.approvePreTranslationReview(
        reportId,
        review.data!.version_id,
      ),
    onSuccess: refresh,
  });

  const requestChanges = useMutation({
    mutationFn: () =>
      api.requestPreTranslationChanges(
        reportId,
        review.data!.version_id,
        notes.trim(),
      ),
    onSuccess: () => {
      setNotes("");
      refresh();
    },
  });

  const reject = useMutation({
    mutationFn: () =>
      api.rejectPreTranslationReview(
        reportId,
        review.data!.version_id,
        notes.trim(),
      ),
    onSuccess: () => {
      setNotes("");
      refresh();
    },
  });

  const actionPending =
    edit.isPending ||
    approve.isPending ||
    requestChanges.isPending ||
    reject.isPending;

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Controlled release
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Human Review
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Pre-translation review state, editable content,
          approval decisions, change requests, rejection,
          and review history are persisted by the backend.
        </p>
      </header>

      <section className="card p-5">
        <div className="muted text-sm">
          Report
        </div>

        <select
          className="input mt-2 min-w-80"
          value={reportId}
          onChange={(event) =>
            setReportId(event.target.value)
          }
        >
          {reports.data?.map((report) => (
            <option
              key={report.id}
              value={report.id}
            >
              {report.topic}
            </option>
          ))}
        </select>
      </section>

      {review.isPending && (
        <div className="card p-6 muted">
          Loading review context…
        </div>
      )}

      {review.error && (
        <div className="card p-6">
          <div
            style={{
              color: "var(--danger)",
            }}
          >
            Review unavailable:{" "}
            {review.error.message}
          </div>

          <div className="muted text-sm mt-2">
            The report may not have a current
            pre-translation review checkpoint yet.
          </div>
        </div>
      )}

      {review.data && (
        <>
          <div className="grid md:grid-cols-4 gap-4">
            <Metric
              label="Status"
              value={review.data.status}
            />

            <Metric
              label="Review stage"
              value={review.data.review_stage}
            />

            <Metric
              label="Version"
              value={
                `v${review.data.version_number}`
              }
            />

            <Metric
              label="Language"
              value={review.data.language}
            />
          </div>

          <section className="card p-5">
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h2 className="font-semibold">
                  Review content
                </h2>

                <div className="muted text-xs mt-1 break-all">
                  Version ID:{" "}
                  {review.data.version_id}
                </div>
              </div>

              {review.data.change_type && (
                <span className="rounded-full border px-3 py-1 text-xs">
                  {review.data.change_type}
                </span>
              )}
            </div>

            <textarea
              className="input mt-4 min-h-[32rem] resize-y"
              value={content}
              onChange={(event) =>
                setContent(event.target.value)
              }
            />

            <div className="muted text-xs mt-2">
              {content.length.toLocaleString()} characters
            </div>

            <label className="block mt-5">
              <div className="muted text-sm">
                Review notes
              </div>

              <textarea
                className="input mt-2 min-h-28 resize-y"
                placeholder="Add notes for the review event…"
                value={notes}
                onChange={(event) =>
                  setNotes(event.target.value)
                }
              />
            </label>

            <div className="flex flex-wrap gap-2 mt-5">
              <button
                className="btn btn-secondary"
                disabled={
                  actionPending ||
                  !content.trim()
                }
                onClick={() =>
                  edit.mutate()
                }
              >
                {edit.isPending
                  ? "Saving…"
                  : "Save edit"}
              </button>

              <button
                className="btn btn-primary"
                disabled={
                  actionPending
                }
                onClick={() =>
                  approve.mutate()
                }
              >
                {approve.isPending
                  ? "Approving…"
                  : "Approve"}
              </button>

              <button
                className="btn btn-secondary"
                disabled={
                  actionPending ||
                  !notes.trim()
                }
                onClick={() =>
                  requestChanges.mutate()
                }
              >
                {requestChanges.isPending
                  ? "Sending…"
                  : "Request changes"}
              </button>

              <button
                className="btn btn-secondary"
                disabled={
                  actionPending ||
                  !notes.trim()
                }
                onClick={() =>
                  reject.mutate()
                }
              >
                {reject.isPending
                  ? "Rejecting…"
                  : "Reject"}
              </button>
            </div>

            {edit.error && (
              <ErrorMessage
                message={edit.error.message}
              />
            )}

            {approve.error && (
              <ErrorMessage
                message={approve.error.message}
              />
            )}

            {requestChanges.error && (
              <ErrorMessage
                message={
                  requestChanges.error.message
                }
              />
            )}

            {reject.error && (
              <ErrorMessage
                message={
                  reject.error.message
                }
              />
            )}
          </section>

          <section className="card overflow-hidden">
            <div
              className="px-5 py-4 border-b"
              style={{
                borderColor: "var(--line)",
              }}
            >
              <div className="font-semibold">
                Review history
              </div>

              <div className="muted text-xs mt-1">
                Backend-persisted review events
              </div>
            </div>

            <div className="divide-y">
              {review.data.review_events
                .slice()
                .reverse()
                .map((event) => (
                  <div
                    key={event.id}
                    className="p-5"
                  >
                    <div className="flex flex-wrap justify-between gap-3">
                      <div>
                        <div className="font-medium">
                          {event.action}
                        </div>

                        <div className="muted text-xs mt-1">
                          {new Date(
                            event.created_at,
                          ).toLocaleString()}
                        </div>
                      </div>

                      <div className="muted text-xs break-all">
                        User: {event.user_id}
                      </div>
                    </div>

                    {event.notes && (
                      <p className="muted text-sm mt-3 whitespace-pre-wrap">
                        {event.notes}
                      </p>
                    )}

                    {event.version_id && (
                      <div className="muted text-xs mt-2 break-all">
                        Version:{" "}
                        {event.version_id}
                      </div>
                    )}
                  </div>
                ))}

              {!review.data.review_events
                .length && (
                <div className="p-8 muted text-sm">
                  No review events recorded yet.
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="card p-5">
      <div className="muted text-sm">
        {label}
      </div>

      <div className="text-xl font-semibold mt-2">
        {value}
      </div>
    </div>
  );
}

function ErrorMessage({
  message,
}: {
  message: string;
}) {
  return (
    <div
      className="text-sm mt-3"
      style={{
        color: "var(--danger)",
      }}
    >
      {message}
    </div>
  );
}