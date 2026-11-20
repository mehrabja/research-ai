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

export type SourceExtraction = components["schemas"]["SourceExtractionResponse"];
export type SourceEmbedding = components["schemas"]["SourceEmbeddingResponse"];

export async function getSource(
  reportId: string,
  sourceId: string,
): Promise<SavedSource> {
  const { data, error } = await api.GET(
    "/api/v1/reports/{report_id}/sources/{source_id}",
    { params: { path: { report_id: reportId, source_id: sourceId } } },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function extractSource(
  reportId: string,
  sourceId: string,
): Promise<SourceExtraction> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/sources/{source_id}/extract",
    {
      params: {
        path: { report_id: reportId, source_id: sourceId },
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function embedSource(
  reportId: string,
  sourceId: string,
): Promise<SourceEmbedding> {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/sources/{source_id}/embed",
    {
      params: {
        path: { report_id: reportId, source_id: sourceId },
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
  return "Sources API request failed";
}
