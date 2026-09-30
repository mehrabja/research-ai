import type { components } from "./schema";
import { api } from "./client";

export type ProjectFile = components["schemas"]["ProjectFileListItem"];
export type ProjectFileRead = components["schemas"]["ProjectFileRead"];
export type Folder = components["schemas"]["FolderRead"];

export async function listProjectFiles(
  projectId: string,
  folderId?: string,
): Promise<{ items: ProjectFile[]; total: number }> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/files",
    {
      params: {
        path: { project_id: projectId },
        query: {
          folder_id: folderId,
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

export async function listProjectFolders(
  projectId: string,
): Promise<Folder[]> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/folders",
    {
      params: {
        path: { project_id: projectId },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data.items;
}

export async function createProjectFolder(
  projectId: string,
  name: string,
  parentId?: string,
): Promise<Folder> {
  const { data, error } = await api.POST(
    "/api/v1/projects/{project_id}/folders",
    {
      params: {
        path: { project_id: projectId },
      },
      body: {
        name,
        parent_id: parentId,
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function uploadProjectFile(
  projectId: string,
  file: File,
  folderId?: string,
): Promise<ProjectFileRead> {
  const form = new FormData();
  form.append("file", file);

  const suffix = folderId
    ? "?folder_id=" + encodeURIComponent(folderId)
    : "";

  const response = await fetch(
    "/api/v1/projects/" + projectId + "/files" + suffix,
    {
      method: "POST",
      body: form,
      credentials: "include",
    },
  );

  if (!response.ok) {
    throw new Error(
      await readResponseError(response, "File upload failed"),
    );
  }

  return (await response.json()) as ProjectFileRead;
}

export async function moveProjectFile(
  fileId: string,
  folderId?: string,
): Promise<ProjectFileRead> {
  const { data, error } = await api.PATCH(
    "/api/v1/files/{file_id}",
    {
      params: {
        path: { file_id: fileId },
      },
      body: {
        folder_id: folderId ?? null,
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function deleteProjectFile(
  fileId: string,
): Promise<void> {
  const { error } = await api.DELETE("/api/v1/files/{file_id}", {
    params: {
      path: { file_id: fileId },
    },
  });

  if (error) {
    throw new Error(getApiErrorMessage(error));
  }
}

export function projectFileContentUrl(
  fileId: string,
  inline = false,
): string {
  const suffix = inline ? "?inline=true" : "";
  return "/api/v1/files/" + fileId + "/content" + suffix;
}

async function readResponseError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      message?: unknown;
      error?: unknown;
    };

    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.message === "string") return payload.message;
    if (typeof payload.error === "string") return payload.error;
  } catch {
    // Ignore malformed error payloads.
  }

  return fallback;
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }

  return "Files API request failed";
}
