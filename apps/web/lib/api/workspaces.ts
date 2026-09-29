import type { components } from "./schema";
import { api } from "./client";
import { apiErrorFromUnknown } from "./errors";

export type Workspace = components["schemas"]["WorkspaceListItem"];

export async function listWorkspaces(): Promise<Workspace[]> {
  const { data, error } = await api.GET("/api/v1/workspaces");

  if (error) {
    throw apiErrorFromUnknown(error, {
      fallback: "Workspace API request failed",
    });
  }

  return data?.items ?? [];
}


export type WorkspaceRead = components["schemas"]["WorkspaceRead"];

async function updateWorkspaceLifecycle(
  action: "suspend" | "reactivate",
  workspaceId: string,
): Promise<WorkspaceRead> {
  const { data, error } = await api.POST(
    action === "suspend"
      ? "/api/v1/workspaces/{workspace_id}/suspend"
      : "/api/v1/workspaces/{workspace_id}/reactivate",
    {
      params: {
        path: { workspace_id: workspaceId },
      },
    },
  );

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      fallback:
        action === "suspend"
          ? "Workspace suspension failed"
          : "Workspace reactivation failed",
    });
  }

  return data;
}

export function suspendWorkspace(
  workspaceId: string,
): Promise<WorkspaceRead> {
  return updateWorkspaceLifecycle("suspend", workspaceId);
}

export function reactivateWorkspace(
  workspaceId: string,
): Promise<WorkspaceRead> {
  return updateWorkspaceLifecycle("reactivate", workspaceId);
}
