import { apiErrorFromResponse } from "./errors";

export type PdfWorkspaceDocument = {
  id: string;
  original_filename: string;
  size_bytes: number;
  status: string;
  extraction_status: string;
  content_url: string;
};

export type PdfAnnotation = {
  id: string;
  project_id: string;
  file_id: string;
  created_by_user: string;
  kind: "highlight" | "note";
  page_number: number;
  selected_text: string | null;
  note: string | null;
  rect: Record<string, unknown> | null;
  annotation_meta: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type PdfWorkspace = {
  id: string;
  project_id: string;
  active_file_id: string | null;
  page_number: number;
  zoom: number;
  scroll_x: number;
  scroll_y: number;
  documents: PdfWorkspaceDocument[];
  annotations: PdfAnnotation[];
  updated_at: string;
};

async function requestJson<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    credentials: "include",
    ...init,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "PDF workspace request failed",
    );
  }
  return (await response.json()) as T;
}

export function getPdfWorkspace(
  projectId: string,
): Promise<PdfWorkspace> {
  return requestJson(
    "/api/v1/projects/" + projectId + "/pdf-workspace",
  );
}

export function savePdfWorkspace(
  projectId: string,
  input: {
    active_file_id: string | null;
    page_number: number;
    zoom: number;
    scroll_x: number;
    scroll_y: number;
  },
): Promise<PdfWorkspace> {
  return requestJson(
    "/api/v1/projects/" + projectId + "/pdf-workspace",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}

export function createPdfAnnotation(
  projectId: string,
  input: {
    file_id: string;
    kind: "highlight" | "note";
    page_number: number;
    selected_text?: string;
    note?: string;
  },
): Promise<PdfAnnotation> {
  return requestJson(
    "/api/v1/projects/" +
      projectId +
      "/pdf-workspace/annotations",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}

export async function deletePdfAnnotation(
  projectId: string,
  annotationId: string,
): Promise<void> {
  const response = await fetch(
    "/api/v1/projects/" +
      projectId +
      "/pdf-workspace/annotations/" +
      annotationId,
    {
      method: "DELETE",
      credentials: "include",
    },
  );
  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "PDF annotation delete failed",
    );
  }
}
