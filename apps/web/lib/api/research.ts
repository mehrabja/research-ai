import type { components } from "./schema";
import { api } from "./client";

export type Report = components["schemas"]["ReportResponse"];
export type SourceCandidate = components["schemas"]["SourceCandidateRead"];

export async function listReports(): Promise<Report[]> {
  const { data, error } = await api.GET("/api/v1/reports", {
    params: {
      query: {},
    },
  });

  if (error) {
    throw new Error(getApiErrorMessage(error));
  }

  return data ?? [];
}

export async function createResearchReport(
  topic: string,
  projectId?: string,
): Promise<Report> {
  const { data, error } = await api.POST("/api/v1/reports", {
    params: {
      query: {},
    },
    body: {
      topic,
      output_language: "en",
      domain: "academic research",
      project_id: projectId,
      tone: "academic",
      length: "medium",
      audience_level: "researcher",
    },
  });

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

export async function searchSources(
  reportId: string,
  query: string,
): Promise<SourceCandidate[]> {
  const { data, error } = await api.GET(
    "/api/v1/reports/{report_id}/sources/search",
    {
      params: {
        path: {
          report_id: reportId,
        },
        query: {
          q: query,
          limit: 10,
          sort_by: "relevance",
          sort_order: "desc",
        },
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data.candidates;
}

export async function saveSource(
  reportId: string,
  candidate: SourceCandidate,
) {
  const { data, error } = await api.POST(
    "/api/v1/reports/{report_id}/sources",
    {
      params: {
        path: {
          report_id: reportId,
        },
      },
      body: {
        source_api: candidate.source_api,
        external_source_id: candidate.external_source_id,
        title: candidate.title,
        authors: candidate.authors,
        year: candidate.year,
        doi: candidate.doi,
        url: candidate.url,
        abstract: candidate.abstract,
        citation_count: candidate.citation_count,
        source_meta: candidate.source_meta,
      },
    },
  );

  if (error || !data) {
    throw new Error(getApiErrorMessage(error));
  }

  return data;
}

function getApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const value = error as {
      detail?: unknown;
      message?: unknown;
    };

    if (typeof value.detail === "string") {
      return value.detail;
    }

    if (typeof value.message === "string") {
      return value.message;
    }
  }

  return "Research API request failed";
}