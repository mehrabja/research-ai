import type { components } from "./schema";
import { api } from "./client";

export type SavedSource = components["schemas"]["SourceRead"];

export async function listSources(reportId: string): Promise<SavedSource[]> {
  const { data, error } = await api.GET(
    "/api/v1/reports/{report_id}/sources",
    {
      params: {
        path: { report_id: reportId },
      },
    },
  );

  if (error) {
    throw new Error(getApiErrorMessage(error));
  }

  return data?.items ?? [];
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }
  return "Sources API request failed";
}
