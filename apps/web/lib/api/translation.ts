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


export interface CurrentTranslation {
  run_id: string;
  translation_version_id: string;
  source_version_id: string | null;
  source_lang: string;
  target_lang: string;
  provider: string;
  status: string;
  completed_at: string | null;
  content: string;
  preservation_check_status: string;
  preservation_details: Record<string, unknown> | null;
}

export async function getCurrentTranslation(
  reportId: string,
): Promise<CurrentTranslation | null> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/translation/current`,
    { credentials: "include", cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await getFetchErrorMessage(response));
  return (await response.json()) as CurrentTranslation;
}

async function getFetchErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Fall through to the generic status message.
  }
  return `Translation request failed (${response.status})`;
}
