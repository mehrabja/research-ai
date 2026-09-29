import type { components } from "./schema";
import { api } from "./client";
import { apiErrorFromUnknown } from "./errors";

export type Project = components["schemas"]["ProjectListItem"];
export type ProjectRead = components["schemas"]["ProjectRead"];
export type ProjectReport = components["schemas"]["ProjectReportListItem"];

export async function listProjects(
  workspaceId?: string,
): Promise<Project[]> {
  const { data, error, response } = await api.GET("/api/v1/projects", {
    params: {
      query: {
        workspace_id: workspaceId,
        include_archived: false,
        limit: 100,
        offset: 0,
      },
    },
  });

  if (error) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Project API request failed",
    });
  }

  return data?.items ?? [];
}

export async function createProject(input: {
  workspaceId?: string;
  name: string;
  description?: string;
}): Promise<ProjectRead> {
  const { data, error } = await api.POST("/api/v1/projects", {
    params: {
      query: {
        workspace_id: input.workspaceId,
      },
    },
    body: {
      name: input.name,
      description: input.description || undefined,
      status: "draft",
    },
  });

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function archiveProject(
  projectId: string,
  workspaceId?: string,
): Promise<ProjectRead> {
  const { data, error } = await api.POST(
    "/api/v1/projects/{project_id}/archive",
    {
      params: {
        path: { project_id: projectId },
        query: { workspace_id: workspaceId },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function listProjectReports(
  projectId: string,
  limit = 50,
): Promise<ProjectReport[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/projects/{project_id}/reports",
    {
      params: {
        path: { project_id: projectId },
        query: {
          workspace_id: undefined,
          limit,
          offset: 0,
        },
      },
    },
  );

  if (error) {
    throw apiErrorFromUnknown(error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Project reports API request failed",
    });
  }

  return data?.items ?? [];
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }

  return "Project API request failed";
}
