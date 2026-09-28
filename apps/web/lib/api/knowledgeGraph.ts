import type { components } from "./schema";
import { api } from "./client";

export type KnowledgeGraph =
  components["schemas"]["KnowledgeGraphRead"];
export type KnowledgeGraphSummary =
  components["schemas"]["KnowledgeGraphSummaryRead"];
export type KnowledgeGraphBuildResponse =
  components["schemas"]["KnowledgeGraphBuildResponse"];

export async function getKnowledgeGraphSummary(
  projectId: string,
): Promise<KnowledgeGraphSummary | null> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/knowledge-graph/summary",
    {
      params: { path: { project_id: projectId } },
    },
  );

  if (error) {
    const status =
      typeof error === "object" && error !== null
        ? (error as { status?: number }).status
        : undefined;
    if (status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }

  return data ?? null;
}

export async function getKnowledgeGraph(
  projectId: string,
): Promise<KnowledgeGraph | null> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/knowledge-graph",
    {
      params: { path: { project_id: projectId } },
    },
  );

  if (error) {
    const status =
      typeof error === "object" && error !== null
        ? (error as { status?: number }).status
        : undefined;
    if (status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }

  return data ?? null;
}

export async function generateKnowledgeGraph(
  projectId: string,
  force = false,
): Promise<KnowledgeGraphBuildResponse> {
  const { data, error } = await api.POST(
    "/api/v1/projects/{project_id}/knowledge-graph/generate",
    {
      params: { path: { project_id: projectId } },
      body: { force, async: false },
    },
  );

  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export function knowledgeGraphExportUrl(projectId: string): string {
  return "/api/v1/projects/" + projectId + "/knowledge-graph/export";
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }
  return "Knowledge graph API request failed";
}
