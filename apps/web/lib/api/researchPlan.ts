import type { components } from "./schema";
import { api } from "./client";

export type ResearchPlan = components["schemas"]["ResearchPlanRead"];
export type ResearchPlanCoverage =
  components["schemas"]["ResearchPlanCoverageRead"];
export type ResearchPlanValidation =
  components["schemas"]["ResearchPlanValidationRead"];
export type ResearchPlanGenerateResponse =
  components["schemas"]["ResearchPlanGenerateResponse"];

export async function listResearchPlanVersions(
  projectId: string,
): Promise<ResearchPlan[]> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/research-plan/versions",
    {
      params: {
        path: { project_id: projectId },
        query: { limit: 20, offset: 0 },
      },
    },
  );

  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data.items;
}

export async function generateResearchPlan(
  projectId: string,
  force = false,
): Promise<ResearchPlanGenerateResponse> {
  const { data, error } = await api.POST(
    "/api/v1/projects/{project_id}/research-plan/generate",
    {
      params: { path: { project_id: projectId } },
      body: { force, async: false },
    },
  );

  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function saveResearchPlanRevision(
  projectId: string,
  input: {
    researchObjectiveSnapshot?: string | null;
    planningMode?: string | null;
    researchQuestionsSnapshot?: unknown[] | null;
    hypothesesSnapshot?: unknown[] | null;
  },
): Promise<ResearchPlan> {
  const { data, error } = await api.PATCH(
    "/api/v1/projects/{project_id}/research-plan",
    {
      params: { path: { project_id: projectId } },
      body: {
        research_objective_snapshot: input.researchObjectiveSnapshot,
        planning_mode: input.planningMode,
        research_questions_snapshot: input.researchQuestionsSnapshot,
        hypotheses_snapshot: input.hypothesesSnapshot,
      },
    },
  );

  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function restoreResearchPlanVersion(
  projectId: string,
  targetVersion: number,
): Promise<ResearchPlan> {
  const { data, error } = await api.POST(
    "/api/v1/projects/{project_id}/research-plan/restore",
    {
      params: { path: { project_id: projectId } },
      body: { target_version: targetVersion },
    },
  );

  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function validateResearchPlan(
  projectId: string,
): Promise<ResearchPlanValidation> {
  const { data, error } = await api.POST(
    "/api/v1/projects/{project_id}/research-plan/validate",
    {
      params: { path: { project_id: projectId } },
    },
  );

  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function getResearchPlanCoverage(
  projectId: string,
): Promise<ResearchPlanCoverage> {
  const { data, error } = await api.GET(
    "/api/v1/projects/{project_id}/research-plan/coverage",
    {
      params: { path: { project_id: projectId } },
    },
  );

  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as { detail?: unknown; message?: unknown };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }
  return "Research plan API request failed";
}
