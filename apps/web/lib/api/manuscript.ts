import type { components } from "./schema";
import { api } from "./client";

export type ManuscriptCurrent =
  components["schemas"]["ManuscriptCurrentRead"];
export type ManuscriptProseCurrent =
  components["schemas"]["ManuscriptProseCurrentRead"];
export type ManuscriptGenerateResponse =
  components["schemas"]["ManuscriptGenerateResponse"];
export type ManuscriptProseGenerateResponse =
  components["schemas"]["ManuscriptProseGenerateResponse"];
export type ManuscriptValidation =
  components["schemas"]["ManuscriptValidationRead"];


export type ManuscriptDraft =
  components["schemas"]["ManuscriptDraftRead"];

export class ManuscriptDraftConflictError extends Error {
  readonly status = 409;

  constructor(message: string) {
    super(message);
    this.name = "ManuscriptDraftConflictError";
  }
}

export async function getManuscriptDraft(
  reportId: string,
): Promise<ManuscriptDraft | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/manuscript/draft",
    { params: { path: { report_id: reportId } } },
  );
  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }
  return data ?? null;
}

export async function saveManuscriptDraft(
  reportId: string,
  input: {
    baseVersionId: string;
    revision: number;
    content: Record<string, unknown>;
  },
): Promise<ManuscriptDraft> {
  const { data, error, response } = await api.PUT(
    "/api/v1/reports/{report_id}/manuscript/draft",
    {
      params: { path: { report_id: reportId } },
      body: {
        base_version_id: input.baseVersionId,
        revision: input.revision,
        content: input.content,
      },
    },
  );
  if (error || !data) {
    const message = getApiErrorMessage(error);
    if (response.status === 409) {
      throw new ManuscriptDraftConflictError(message);
    }
    throw new Error(message);
  }
  return data;
}

export async function commitManuscriptDraft(
  reportId: string,
  baseVersionId: string,
  revision: number,
): Promise<components["schemas"]["app__schemas__manuscript__ManuscriptVersionRead"]> {
  const { data, error, response } = await api.POST(
    "/api/v1/reports/{report_id}/manuscript/draft/commit",
    {
      params: { path: { report_id: reportId } },
      body: {
        base_version_id: baseVersionId,
        revision,
      },
    },
  );
  if (error || !data) {
    const message = getApiErrorMessage(error);
    if (response.status === 409) {
      throw new ManuscriptDraftConflictError(message);
    }
    throw new Error(message);
  }
  return data;
}

export async function discardManuscriptDraft(
  reportId: string,
): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/reports/{report_id}/manuscript/draft",
    { params: { path: { report_id: reportId } } },
  );
  if (error || !response.ok) {
    throw new Error(getApiErrorMessage(error));
  }
}

export async function getCurrentManuscript(
  reportId: string,
): Promise<ManuscriptCurrent | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/manuscript",
    { params: { path: { report_id: reportId } } },
  );
  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }
  return data ?? null;
}

export async function listManuscriptVersions(
  reportId: string,
): Promise<components["schemas"]["app__schemas__manuscript__ManuscriptVersionRead"][]> {
  const { data, error } = await api.GET(
    "/api/v1/reports/{report_id}/manuscript/versions",
    {
      params: {
        path: { report_id: reportId },
        query: { limit: 50, offset: 0 },
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data.items;
}

export async function generateManuscript(
  reportId: string,
  force = false,
): Promise<ManuscriptGenerateResponse> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/manuscript/generate",
    {
      params: { path: { report_id: reportId } },
      body: { force, async: false },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function validateManuscript(
  reportId: string,
): Promise<ManuscriptValidation> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/manuscript/validate",
    { params: { path: { report_id: reportId } } },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function getCurrentManuscriptProse(
  reportId: string,
): Promise<ManuscriptProseCurrent | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/manuscript/prose/current",
    { params: { path: { report_id: reportId } } },
  );
  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }
  return data ?? null;
}

export async function generateManuscriptProse(
  reportId: string,
  baseManuscriptVersionId: string,
  mode = "evidence_grounded",
): Promise<ManuscriptProseGenerateResponse> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/manuscript/prose/generate",
    {
      params: { path: { report_id: reportId } },
      body: {
        base_manuscript_version_id: baseManuscriptVersionId,
        mode,
        force: false,
        async: false,
      },
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
  return "Manuscript API request failed";
}
