import type { components } from "./schema";
import { api } from "./client";

export type PreTranslationReview =
  components["schemas"]["PreTranslationReviewResponse"];
export type ReviewEvent = components["schemas"]["ReviewEventResponse"];

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

export async function editPreTranslationReview(
  reportId: string,
  versionId: string,
  content: string,
  notes?: string,
): Promise<PreTranslationReview> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/review/pre-translation/edit",
    {
      params: { path: { report_id: reportId } },
      body: {
        version_id: versionId,
        content,
        notes: notes?.trim() ? notes.trim() : null,
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
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

export async function requestChangesPreTranslationReview(
  reportId: string,
  versionId: string,
  notes: string,
): Promise<PreTranslationReview> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/review/pre-translation/request-changes",
    {
      params: { path: { report_id: reportId } },
      body: { version_id: versionId, notes: notes.trim() },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function rejectPreTranslationReview(
  reportId: string,
  versionId: string,
  notes: string,
): Promise<PreTranslationReview> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/review/pre-translation/reject",
    {
      params: { path: { report_id: reportId } },
      body: { version_id: versionId, notes: notes.trim() },
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
  return "Translation review API request failed";
}
