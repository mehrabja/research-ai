export interface PostTranslationHumanizationRun {
  id: string;
  report_id: string;
  manuscript_id: string | null;
  manuscript_version_id: string | null;
  stage: string;
  language: string;
  status: string;
  mode: string | null;
  m32_version: string | null;
  context_hash: string | null;
  gate: string | null;
  preservation_summary: Record<string, unknown> | null;
  cost_usd: number | null;
  tokens_used: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface CurrentPostTranslationHumanization {
  run: PostTranslationHumanizationRun;
  translated_version_id: string | null;
  output_version_id: string | null;
}

export interface EnqueuePostTranslationHumanizationResponse {
  job_id: string | null;
  status: string;
}

export async function getCurrentPostTranslationHumanization(
  reportId: string,
): Promise<CurrentPostTranslationHumanization | null> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/post-translation-humanization/current`,
    { credentials: "include", cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as CurrentPostTranslationHumanization;
}

export async function enqueuePostTranslationHumanization(
  reportId: string,
  translationRunId: string,
  translationVersionId: string,
): Promise<EnqueuePostTranslationHumanizationResponse> {
  const response = await fetch(
    `/api/v1/reports/${reportId}/post-translation-humanization/enqueue`,
    {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        translation_run_id: translationRunId,
        translation_version_id: translationVersionId,
      }),
    },
  );
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return (await response.json()) as EnqueuePostTranslationHumanizationResponse;
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Fall through to the generic HTTP status.
  }
  return `Post-translation humanization request failed (${response.status})`;
}
