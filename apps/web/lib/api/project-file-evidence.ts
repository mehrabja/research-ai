import { apiErrorFromResponse } from "./errors";

export type ProjectFileEvidence = {
  file_id: string;
  project_id: string;
  filename: string;
  file_kind: string;
  extraction_status: string;
  evidence_status:
    | "processing"
    | "synced"
    | "awaiting_report"
    | "unavailable";
  source_count: number;
  chunk_count: number;
  source_ids: string[];
  report_ids: string[];
  last_synced_at: string | null;
};

export async function getProjectFileEvidence(
  projectId: string,
): Promise<{ items: ProjectFileEvidence[]; total: number }> {
  const response = await fetch(
    "/api/v1/projects/" + projectId + "/evidence/files",
    { credentials: "include" },
  );
  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "File evidence request failed",
    );
  }
  return (await response.json()) as {
    items: ProjectFileEvidence[];
    total: number;
  };
}

export async function syncProjectFileEvidence(
  projectId: string,
  reportId?: string,
): Promise<{ synced_reports: number; synced_files: number }> {
  const response = await fetch(
    "/api/v1/projects/" + projectId + "/evidence/sync",
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_id: reportId ?? null }),
    },
  );
  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "File evidence synchronization failed",
    );
  }
  return (await response.json()) as {
    synced_reports: number;
    synced_files: number;
  };
}
