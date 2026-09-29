export interface PublicationTarget {
  id: string;
  target_code: string;
  profile_version: string;
  publisher: string | null;
  venue: string;
  venue_type: string;
  citation_style: string;
  active: boolean;
  profile_schema_version: string;
  effective_from: string | null;
  effective_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublicationTargetSelection {
  id: string;
  report_id: string;
  target_id: string;
  selected_by: string | null;
  selection_note: string | null;
  created_at: string;
}

export interface PublicationComplianceRun {
  id: string;
  project_id: string;
  report_id: string;
  manuscript_id: string | null;
  manuscript_version_id: string;
  target_id: string;
  context_hash: string;
  m33_version: string;
  rules_version: string;
  target_profile_version: string;
  status: string;
  finding_count: number;
  blocking_count: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  gate: string | null;
  checklist_state: Record<string, unknown> | null;
  formatting_summary: Record<string, unknown> | null;
  warnings: unknown[] | null;
  error_message: string | null;
  duration_ms: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface PublicationComplianceFinding {
  id: string;
  compliance_run_id: string;
  rule_id: string;
  category: string;
  severity: string;
  title: string;
  message: string;
  location: Record<string, unknown> | null;
  evidence: Record<string, unknown> | null;
  remediation: Record<string, unknown> | null;
  created_at: string;
}

export interface PublicationComplianceValidation {
  validation_status: string;
  validation_errors: string[];
  warnings: string[];
  gate: string | null;
}

export interface PublicationComplianceResponse {
  status: string;
  job_id: string | null;
  run_id: string | null;
  context_hash: string | null;
  gate: string | null;
  finding_count: number | null;
  blocking_count: number | null;
}

async function request<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as T;
}

export async function listPublicationTargets(): Promise<PublicationTarget[]> {
  const data = await request<{
    items: PublicationTarget[];
    total: number;
    limit: number;
    offset: number;
  }>("/api/v1/publication-targets?active_only=true&limit=100&offset=0");
  return data.items;
}

export async function getCurrentPublicationTarget(
  reportId: string,
): Promise<PublicationTargetSelection | null> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/publication-target/current`,
    { credentials: "include", cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as PublicationTargetSelection;
}

export async function selectPublicationTarget(
  reportId: string,
  targetId: string,
  selectionNote?: string,
): Promise<PublicationTargetSelection> {
  return request<PublicationTargetSelection>(
    `/api/v1/reports/${reportId}/publication-target/select`,
    {
      method: "POST",
      body: JSON.stringify({
        target_id: targetId,
        selection_note: selectionNote?.trim() || null,
      }),
    },
  );
}

export async function getCurrentPublicationCompliance(
  reportId: string,
): Promise<{ run: PublicationComplianceRun } | null> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/publication-compliance/current`,
    { credentials: "include", cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as { run: PublicationComplianceRun };
}

export async function generatePublicationCompliance(
  reportId: string,
  manuscriptVersionId: string,
  targetId: string,
  force = false,
): Promise<PublicationComplianceResponse> {
  return request<PublicationComplianceResponse>(
    `/api/v1/reports/${reportId}/publication-compliance/generate`,
    {
      method: "POST",
      body: JSON.stringify({
        manuscript_version_id: manuscriptVersionId,
        target_id: targetId,
        force,
        async: false,
      }),
    },
  );
}

export async function getPublicationFindings(
  reportId: string,
): Promise<PublicationComplianceFinding[]> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/publication-compliance/findings?limit=200&offset=0`,
    { credentials: "include", cache: "no-store" },
  );
  if (response.status === 404) return [];
  if (!response.ok) throw new Error(await getErrorMessage(response));
  const data = (await response.json()) as {
    items: PublicationComplianceFinding[];
  };
  return data.items;
}

export async function getPublicationChecklist(
  reportId: string,
): Promise<{
  run_id: string;
  target_id: string;
  target_profile_version: string;
  gate: string | null;
  checklist_state: Record<string, unknown> | null;
} | null> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/publication-compliance/checklist`,
    { credentials: "include", cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as {
    run_id: string;
    target_id: string;
    target_profile_version: string;
    gate: string | null;
    checklist_state: Record<string, unknown> | null;
  };
}

export async function validatePublicationCompliance(
  reportId: string,
): Promise<PublicationComplianceValidation> {
  return request<PublicationComplianceValidation>(
    `/api/v1/reports/${reportId}/publication-compliance/validate`,
    { method: "POST" },
  );
}

export async function downloadPublication(
  reportId: string,
  format: "markdown" | "html" | "json" | "docx",
): Promise<void> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/publication/export?format=${encodeURIComponent(format)}`,
    {
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "*/*" },
    },
  );
  if (!response.ok) throw new Error(await getErrorMessage(response));

  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/i);
  const filename = match?.[1] ?? `research-report.${format === "markdown" ? "md" : format}`;

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown; message?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (typeof body.message === "string") return body.message;
  } catch {
    // Fall through to the generic HTTP status.
  }
  return `Publication request failed (${response.status})`;
}
