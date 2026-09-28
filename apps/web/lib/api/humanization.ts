import type { components } from "./schema";
import { api } from "./client";

export type HumanizationCurrent =
  components["schemas"]["ManuscriptHumanizationCurrentRead"];
export type HumanizationRun =
  components["schemas"]["HumanizationRunRead"];
export type HumanizationResponse =
  components["schemas"]["ManuscriptHumanizationResponse"];
export type HumanizationValidation =
  components["schemas"]["ManuscriptHumanizationValidationRead"];

export async function getCurrentManuscriptHumanization(
  reportId: string,
): Promise<HumanizationCurrent | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/manuscript-humanization/current",
    { params: { path: { report_id: reportId } } },
  );
  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }
  return data ?? null;
}

export async function generateManuscriptHumanization(
  reportId: string,
  manuscriptVersionId: string,
  mode: string,
): Promise<HumanizationResponse> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/manuscript-humanization/generate",
    {
      params: { path: { report_id: reportId } },
      body: {
        manuscript_version_id: manuscriptVersionId,
        mode,
        force: false,
        async: false,
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function validateManuscriptHumanization(
  reportId: string,
): Promise<HumanizationValidation> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/manuscript-humanization/validate",
    { params: { path: { report_id: reportId } } },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function listManuscriptHumanizationRuns(
  reportId: string,
): Promise<HumanizationRun[]> {
  const { data, error } = await api.GET(
    "/api/v1/reports/{report_id}/manuscript-humanization/runs",
    {
      params: {
        path: { report_id: reportId },
        query: { limit: 20, offset: 0 },
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data.items;
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }
  return "Humanization API request failed";
}
