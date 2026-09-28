import type { components } from "./schema";
import { api } from "./client";

export type LiteratureItem = components["schemas"]["LiteratureItemRead"];
export type LiteratureCluster = components["schemas"]["LiteratureClusterRead"];
export type LiteratureGap = components["schemas"]["LiteratureGapRead"];
export type LiteratureRun = components["schemas"]["LiteratureRunRead"];
export type LiteratureAnalyzeResponse =
  components["schemas"]["LiteratureAnalyzeResponse"];

export async function listLiterature(
  projectId: string,
  screeningStatus?: string,
): Promise<{ items: LiteratureItem[]; total: number }> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/literature",
    {
      params: {
        path: { project_id: projectId },
        query: {
          screening_status: screeningStatus,
          limit: 100,
          offset: 0,
        },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return { items: data.items, total: data.total };
}

export async function listLiteratureClusters(
  projectId: string,
): Promise<LiteratureCluster[]> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/literature/clusters",
    {
      params: {
        path: { project_id: projectId },
        query: { limit: 100, offset: 0 },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data.items;
}

export async function listLiteratureGaps(
  projectId: string,
): Promise<LiteratureGap[]> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/literature/gaps",
    {
      params: {
        path: { project_id: projectId },
        query: { limit: 100, offset: 0 },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data.items;
}

export async function analyzeLiterature(
  projectId: string,
  force = false,
): Promise<LiteratureAnalyzeResponse> {
  const { data, error } = await api.POST(
    "/api/v1/projects/{project_id}/literature/analyze",
    {
      params: { path: { project_id: projectId } },
      body: { force },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function updateLiteratureScreening(
  projectId: string,
  itemId: string,
  screeningStatus:
    | "discovered"
    | "candidate"
    | "included"
    | "excluded"
    | "uncertain",
  reason?: string,
): Promise<LiteratureItem> {
  const { data, error } = await api.PATCH(
    "/api/v1/projects/{project_id}/literature/{item_id}",
    {
      params: {
        path: {
          project_id: projectId,
          item_id: itemId,
        },
      },
      body: {
        screening_status: screeningStatus,
        reason: reason || undefined,
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }

  return "Literature API request failed";
}
