import type { components } from "./schema";
import { api } from "./client";

export type EvidenceMatrix = components["schemas"]["EvidenceMatrixRead"];
export type EvidenceRow = components["schemas"]["EvidenceMatrixRow"];

export async function getEvidenceMatrix(
  reportId: string,
): Promise<EvidenceMatrix | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/evidence/matrix",
    {
      params: {
        path: { report_id: reportId },
      },
    },
  );

  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }

  return data ?? null;
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }

  return "Evidence API request failed";
}
