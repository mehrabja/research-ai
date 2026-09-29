import { apiErrorFromResponse } from "./errors";

export type CanvasNode = {
  id: string;
  type: "idea" | "evidence" | "draft" | "note";
  title: string;
  body: string;
  x: number;
  y: number;
};

export type CanvasEdge = {
  id: string;
  source: string;
  target: string;
};

export type CanvasViewport = {
  x: number;
  y: number;
  zoom: number;
};

export type ResearchCanvas = {
  id: string;
  project_id: string;
  revision: number;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  viewport: CanvasViewport;
  updated_by_user: string | null;
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
      "Research canvas request failed",
    );
  }
  return (await response.json()) as T;
}

export function getResearchCanvas(
  projectId: string,
): Promise<ResearchCanvas> {
  return requestJson(
    "/api/v1/projects/" + projectId + "/research-canvas",
  );
}

export function saveResearchCanvas(
  projectId: string,
  input: {
    nodes: CanvasNode[];
    edges: CanvasEdge[];
    viewport: CanvasViewport;
    expected_revision?: number;
  },
): Promise<ResearchCanvas> {
  return requestJson(
    "/api/v1/projects/" + projectId + "/research-canvas",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}
