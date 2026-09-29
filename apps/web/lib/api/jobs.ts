import type { components } from "./schema";
import { api } from "./client";
import { apiErrorFromUnknown } from "./errors";

export type Job = components["schemas"]["JobResponse"];
export type JobStatus =
  | "queued"
  | "processing"
  | "retrying"
  | "completed"
  | "failed"
  | "cancelled";

const ACTIVE_STATUSES: JobStatus[] = [
  "queued",
  "processing",
  "retrying",
];

export function isActiveJobStatus(status: string): boolean {
  return ACTIVE_STATUSES.includes(status as JobStatus);
}

export async function listJobs(options?: {
  status?: JobStatus;
  limit?: number;
}): Promise<Job[]> {
  const { data, error, response } = await api.GET("/api/v1/jobs", {
    params: {
      query: {
        status: options?.status,
        limit: options?.limit ?? 100,
      },
    },
  });

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Jobs API request failed",
    });
  }

  return data;
}

export async function retryJob(jobId: string): Promise<Job> {
  const { data, error, response } = await api.POST(
    "/api/v1/jobs/{job_id}/retry",
    { params: { path: { job_id: jobId } } },
  );

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Job retry failed",
    });
  }

  return data;
}

export async function cancelJob(
  jobId: string,
): Promise<components["schemas"]["JobCancelResponse"]> {
  const { data, error, response } = await api.POST(
    "/api/v1/jobs/{job_id}/cancel",
    { params: { path: { job_id: jobId } } },
  );

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Job cancellation failed",
    });
  }

  return data;
}
