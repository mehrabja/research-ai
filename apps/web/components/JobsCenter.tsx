"use client";

import { useMemo } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  cancelJob,
  isActiveJobStatus,
  listJobs,
  retryJob,
  type Job,
} from "@/lib/api/jobs";

function formatDate(value: string | null): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

function statusClass(status: string): string {
  if (status === "completed") return "tag success";
  if (status === "failed") return "tag danger";
  if (status === "cancelled") return "tag";
  return "tag warn";
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

export function JobsCenter() {
  const queryClient = useQueryClient();
  const jobsQuery = useQuery({
    queryKey: ["jobs", "all"],
    queryFn: () => listJobs(),
    refetchInterval: (query) => {
      const jobs = (query.state.data ?? []) as Job[];
      return jobs.some((job) => isActiveJobStatus(job.status))
        ? 3_000
        : false;
    },
  });

  const retryMutation = useMutation({
    mutationFn: retryJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["jobs"],
      });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: cancelJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["jobs"],
      });
    },
  });

  const jobs = useMemo(
    () => jobsQuery.data ?? [],
    [jobsQuery.data],
  );
  const running = jobs.filter(
    (job) => job.status === "processing",
  ).length;
  const queued = jobs.filter((job) =>
    ["queued", "retrying"].includes(job.status),
  ).length;
  const succeededToday = useMemo(() => {
    const today = new Date().toDateString();
    return jobs.filter(
      (job) =>
        job.status === "completed" &&
        job.completed_at &&
        new Date(job.completed_at).toDateString() === today,
    ).length;
  }, [jobs]);
  const failed = jobs.filter((job) => job.status === "failed").length;
  const error =
    [jobsQuery.error, retryMutation.error, cancelMutation.error].find(
      (value): value is Error => value instanceof Error,
    );

  const loading = jobsQuery.isPending;

  return (
    <>
      {loading && (
        <section className="card pad" aria-busy="true">
          <h2>Loading job center…</h2>
          <p className="muted">
            Reading durable job state from the API.
          </p>
        </section>
      )}

      {error && (
        <section className="card pad" role="alert">
          <div className="row">
            <div>
              <h3>Job operation failed</h3>
              <p className="muted small">{error.message}</p>
            </div>
            <button
              className="btn ghost"
              type="button"
              onClick={() => void jobsQuery.refetch()}
            >
              Retry
            </button>
          </div>
        </section>
      )}

      <div className="grid grid-4">
        <div className="card metric">
          <div className="label">Running</div>
          <div className="value">{loading ? "…" : running}</div>
          <div className="delta">Server-side processing</div>
        </div>
        <div className="card metric">
          <div className="label">Queued</div>
          <div className="value">{loading ? "…" : queued}</div>
          <div className="delta">Waiting or retrying</div>
        </div>
        <div className="card metric">
          <div className="label">Succeeded today</div>
          <div className="value">{loading ? "…" : succeededToday}</div>
          <div className="delta good">Persisted completed jobs</div>
        </div>
        <div className="card metric">
          <div className="label">Failed</div>
          <div className="value">{loading ? "…" : failed}</div>
          <div className="delta bad">Eligible failures shown below</div>
        </div>
      </div>

      <div className="card table-wrap" style={{ marginTop: 16 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Status</th>
              <th>Attempts</th>
              <th>Created</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6}>
                  <div className="empty" aria-busy="true">
                    <div>Loading durable jobs…</div>
                  </div>
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
              <tr key={job.id}>
                <td>
                  <div className="strong">{job.job_type}</div>
                  {job.last_error_message && (
                    <div
                      className="meta"
                      style={{ marginTop: 4 }}
                    >
                      {job.last_error_code ?? "error"}:{" "}
                      {job.last_error_message}
                    </div>
                  )}
                </td>
                <td>
                  <span className={statusClass(job.status)}>
                    {statusLabel(job.status)}
                  </span>
                </td>
                <td>
                  {job.attempt_count} / {job.max_attempts}
                </td>
                <td>{formatDate(job.created_at)}</td>
                <td>{formatDate(job.updated_at)}</td>
                <td>
                  <div className="actions">
                    {(job.status === "failed" ||
                      job.status === "cancelled") && (
                      <button
                        className="btn ghost"
                        type="button"
                        disabled={
                          retryMutation.isPending &&
                          retryMutation.variables === job.id
                        }
                        onClick={() => retryMutation.mutate(job.id)}
                      >
                        {retryMutation.isPending &&
                        retryMutation.variables === job.id
                          ? "Retrying…"
                          : "Retry"}
                      </button>
                    )}
                    {(job.status === "queued" ||
                      job.status === "retrying") && (
                      <button
                        className="btn ghost"
                        type="button"
                        disabled={
                          cancelMutation.isPending &&
                          cancelMutation.variables === job.id
                        }
                        onClick={() => cancelMutation.mutate(job.id)}
                      >
                        {cancelMutation.isPending &&
                        cancelMutation.variables === job.id
                          ? "Cancelling…"
                          : "Cancel"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
              )
            )}
            {!loading && jobs.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <div className="empty">
                    <div className="big">∅</div>
                    <div>No durable jobs are visible for this account.</div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}