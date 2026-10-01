import type { components } from "./schema";
import { api } from "./client";

export type CodeAnalysis = components["schemas"]["CodeAnalysisRead"];
export type CodeSymbol = components["schemas"]["CodeSymbolRead"];
export type CodeDependency = components["schemas"]["CodeDependencyRead"];
export type DataProfile = components["schemas"]["DataProfileRead"];
export type DataColumnProfile = components["schemas"]["DataColumnProfileRead"];

export type FileIntelligenceKind = "code" | "data";

export async function getProjectFile(
  fileId: string,
): Promise<components["schemas"]["ProjectFileRead"]> {
  const { data, error } = await api.GET("/api/v1/files/{file_id}", {
    params: { path: { file_id: fileId } },
  });
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function getCodeAnalysis(fileId: string): Promise<CodeAnalysis> {
  const { data, error } = await api.GET(
    "/api/v1/files/{file_id}/code-analysis",
    { params: { path: { file_id: fileId } } },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function listCodeSymbols(
  fileId: string,
  limit = 100,
  offset = 0,
): Promise<{ items: CodeSymbol[]; total: number }> {
  const { data, error } = await api.GET(
    "/api/v1/files/{file_id}/code-symbols",
    {
      params: {
        path: { file_id: fileId },
        query: { limit, offset },
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function listCodeDependencies(
  fileId: string,
  limit = 100,
  offset = 0,
): Promise<{ items: CodeDependency[]; total: number }> {
  const { data, error } = await api.GET(
    "/api/v1/files/{file_id}/code-dependencies",
    {
      params: {
        path: { file_id: fileId },
        query: { limit, offset },
      },
    },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function getDataProfile(fileId: string): Promise<DataProfile> {
  const { data, error } = await api.GET(
    "/api/v1/files/{file_id}/data-profile",
    { params: { path: { file_id: fileId } } },
  );
  if (error || !data) throw new Error(getApiErrorMessage(error));
  return data;
}

export async function listDataColumns(
  fileId: string,
  limit = 200,
  offset = 0,
): Promise<{ items: DataColumnProfile[]; total: number }> {
  const { data, error } = await api.GET(
    "/api/v1/files/{file_id}/data-columns",
    {
      params: {
        path: { file_id: fileId },
        query: { limit, offset },
      },
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
  return "File intelligence request failed";
}
