import type { components } from "./schema";
import { api } from "./client";

export type Report = components["schemas"]["ReportResponse"];

export async function getReport(reportId: string): Promise<Report> {
  const { data, error } = await api.GET("/api/v1/reports/{report_id}", {
    params: { path: { report_id: reportId } },
  });
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function listWorkspaceReports(
  workspaceId: string,
): Promise<Report[]> {
  const { data, error } = await api.GET("/api/v1/reports", {
    params: { query: { workspace_id: workspaceId } },
  });
  if (error) throw new Error(getApiErrorMessage(error));
  return data ?? [];
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }
  return "Report API request failed";
}
