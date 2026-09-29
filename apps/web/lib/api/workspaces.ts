import type { components } from "./schema";
import { api } from "./client";
import { apiErrorFromUnknown } from "./errors";

export type Workspace = components["schemas"]["WorkspaceListItem"];

export async function listWorkspaces(): Promise<Workspace[]> {
  const { data, error, response } = await api.GET("/api/v1/workspaces");

  if (error) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Workspace API request failed",
    });
  }

  return data?.items ?? [];
}

