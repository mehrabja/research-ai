import type { components } from "./schema";
import { api } from "./client";

export type Workspace = components["schemas"]["WorkspaceListItem"];

export async function listWorkspaces(): Promise<Workspace[]> {
  const { data, error } = await api.GET("/api/v1/workspaces");

  if (error) {
    throw new Error(getApiErrorMessage(error));
  }

  return data?.items ?? [];
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }

  return "Workspace API request failed";
}
