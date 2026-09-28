export interface FinalReviewEvent {
  id: string;
  action: string;
  user_id: string;
  version_id: string | null;
  notes: string | null;
  created_at: string;
}

export interface FinalReview {
  report_id: string;
  status: string;
  version_id: string;
  version_number: number;
  language: string;
  content: string;
  change_type: string | null;
  source_version_id: string | null;
  review_stage: string;
  review_events: FinalReviewEvent[];
}

async function request<T>(
  reportId: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/review/final${path}`,
    {
      ...init,
      credentials: "include",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
    },
  );
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as T;
}

export async function getFinalReview(
  reportId: string,
): Promise<FinalReview | null> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/review/final`,
    { credentials: "include", cache: "no-store" },
  );
  if (response.status === 404 || response.status === 409) return null;
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as FinalReview;
}

export async function editFinalReview(
  reportId: string,
  versionId: string,
  content: string,
  notes?: string,
): Promise<FinalReview> {
  return request<FinalReview>(reportId, "/edit", {
    method: "POST",
    body: JSON.stringify({
      version_id: versionId,
      content,
      notes: notes?.trim() ? notes.trim() : null,
    }),
  });
}

export async function approveFinalReview(
  reportId: string,
  versionId: string,
): Promise<FinalReview> {
  return request<FinalReview>(reportId, "/approve", {
    method: "POST",
    body: JSON.stringify({ version_id: versionId }),
  });
}

export async function requestChangesFinalReview(
  reportId: string,
  versionId: string,
  notes: string,
): Promise<FinalReview> {
  return request<FinalReview>(reportId, "/request-changes", {
    method: "POST",
    body: JSON.stringify({ version_id: versionId, notes: notes.trim() }),
  });
}

export async function rejectFinalReview(
  reportId: string,
  versionId: string,
  notes: string,
): Promise<FinalReview> {
  return request<FinalReview>(reportId, "/reject", {
    method: "POST",
    body: JSON.stringify({ version_id: versionId, notes: notes.trim() }),
  });
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Fall through to the generic HTTP status.
  }
  return `Final review request failed (${response.status})`;
}
