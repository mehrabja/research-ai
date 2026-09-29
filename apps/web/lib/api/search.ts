import type { components } from "./schema";
import { api } from "./client";
import { apiErrorFromUnknown } from "./errors";

export type SearchResult = components["schemas"]["SearchResult"];
export type SearchResponse = components["schemas"]["SearchResponse"];

export async function searchWorkspace(
  workspaceId: string,
  query: string,
  limit = 50,
): Promise<SearchResponse> {
  const { data, error } = await api.GET("/api/v1/search", {
    params: {
      query: {
        q: query.trim(),
        workspace_id: workspaceId,
        limit,
      },
    },
  });

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      fallback: "Workspace search request failed.",
    });
  }

  return data;
}
