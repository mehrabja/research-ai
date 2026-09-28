import type { components } from "./schema";
import { api } from "./client";

export type CitationCurrent =
  components["schemas"]["CitationCurrentRead"];
export type CitationRun =
  components["schemas"]["CitationRunRead"];
export type CitationValidation =
  components["schemas"]["CitationValidationRead"];
export type Bibliography =
  components["schemas"]["BibliographyRead"];
export type EvidenceMatrix =
  components["schemas"]["EvidenceMatrixRead"];

export async function getCurrentCitations(
  reportId: string,
): Promise<CitationCurrent | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/citations/current",
    { params: { path: { report_id: reportId } } },
  );
  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }
  return data ?? null;
}

export async function getCitationHistory(
  reportId: string,
): Promise<CitationRun[]> {
  const { data, error } = await api.GET(
    "/api/v1/reports/{report_id}/citations/history",
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

export async function getCitationEvidenceMatrix(
  reportId: string,
): Promise<EvidenceMatrix | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/evidence/matrix",
    { params: { path: { report_id: reportId } } },
  );
  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }
  return data ?? null;
}

export async function validateCitations(
  reportId: string,
): Promise<CitationValidation> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/citations/validate",
    { params: { path: { report_id: reportId } } },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function generateCitations(
  reportId: string,
  manuscriptVersionId: string,
  citationStyle: "author_year" | "numeric",
): Promise<components["schemas"]["CitationGenerateResponse"]> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/citations/generate",
    {
      params: { path: { report_id: reportId } },
      body: {
        manuscript_version_id: manuscriptVersionId,
        citation_style: citationStyle,
        force: false,
        async: false,
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function getBibliography(
  reportId: string,
  citationStyle: "author_year" | "numeric",
): Promise<Bibliography | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/reports/{report_id}/citations/bibliography",
    {
      params: {
        path: { report_id: reportId },
        query: { citation_style: citationStyle },
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
  return "Citation API request failed";
}
