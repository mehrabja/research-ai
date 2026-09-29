import type { components } from "./schema";
import { api } from "./client";
import { apiErrorFromUnknown } from "./errors";

export type Report = components["schemas"]["ReportResponse"];

export async function getReport(reportId: string): Promise<Report> {
  const { data, error, response } = await api.GET("/api/v1/reports/{report_id}", {
    params: { path: { report_id: reportId } },
  });
  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Report API request failed",
    });
  }
  return data;
}

export async function listWorkspaceReports(
  workspaceId: string,
): Promise<Report[]> {
  const { data, error, response } = await api.GET("/api/v1/reports", {
    params: { query: { workspace_id: workspaceId } },
  });
  if (error) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Report API request failed",
    });
  }
  return data ?? [];
}

