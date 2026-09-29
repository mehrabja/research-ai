import type { components } from "./schema";
import { api } from "./client";

export type KnowledgeGraph =
  components["schemas"]["KnowledgeGraphRead"];
export type KnowledgeGraphSummary =
  components["schemas"]["KnowledgeGraphSummaryRead"];
export type KnowledgeGraphBuildResponse =
  components["schemas"]["KnowledgeGraphBuildResponse"];

export type KnowledgeGraphNode =
  components["schemas"]["KnowledgeGraphNodeRead"];
export type KnowledgeGraphNeighbor =
  components["schemas"]["KnowledgeGraphNeighborRead"];

export async function listKnowledgeGraphNodes(
  projectId: string,
  options: {
    nodeType?: string;
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<KnowledgeGraphNode[]> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/knowledge-graph/nodes",
    {
      params: {
        path: { project_id: projectId },
        query: {
          node_type: options.nodeType,
          q: options.q,
          limit: options.limit ?? 100,
          offset: options.offset ?? 0,
        },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function getKnowledgeGraphNeighbors(
  projectId: string,
  nodeId: string,
  options: {
    direction?: "in" | "out" | "both";
    relationTypes?: string[];
    limit?: number;
  } = {},
): Promise<KnowledgeGraphNeighbor[]> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/knowledge-graph/nodes/{node_id}/neighbors",
    {
      params: {
        path: {
          project_id: projectId,
          node_id: nodeId,
        },
        query: {
          direction: options.direction ?? "both",
          relation_types: options.relationTypes,
          limit: options.limit ?? 50,
        },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function getKnowledgeGraphSummary(
  projectId: string,
): Promise<KnowledgeGraphSummary | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/projects/{project_id}/knowledge-graph/summary",
    {
      params: { path: { project_id: projectId } },
    },
  );

  if (error) {
    if (response.status === 404) return null;
    throw new Error(getApiErrorMessage(error));
  }

  return data ?? null;
}

export async function getKnowledgeGraph(
  projectId: string,
): Promise<KnowledgeGraph | null> {
  const { data, error, response } = await api.GET(
    "/api/v1/projects/{project_id}/knowledge-graph",
    {
      params: { path: { project_id: projectId } },
    },
  );

  if (error) {
    if (response.status === 404) return null;
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
