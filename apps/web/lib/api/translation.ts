import type { components } from "./schema";
import { api } from "./client";

export type PreTranslationReview =
  components["schemas"]["PreTranslationReviewResponse"];

export async function getPreTranslationReview(
  reportId: string,
): Promise<PreTranslationReview | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/review/pre-translation",
    { params: { path: { report_id: reportId } } },
  );
  if (error) {
    if (response.status === 404 || response.status === 409) return null;
    throw new Error(getApiErrorMessage(error));
  }
  return data ?? null;
}

export async function approvePreTranslationReview(
  reportId: string,
  versionId: string,
): Promise<PreTranslationReview> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/review/pre-translation/approve",
    {
      params: { path: { report_id: reportId } },
      body: { version_id: versionId },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }
  return "Translation API request failed";
}
