import type { components } from "./schema";
import { api } from "./client";

export type Report = components["schemas"]["ReportResponse"];
export type SourceCandidate = components["schemas"]["SourceCandidateRead"];

export type SourceSearchFilters = {
  year?: number;
  openAccess?: boolean;
  minCitations?: number;
  maxCitations?: number;
  author?: string;
  venue?: string;
  yearFrom?: number;
  yearTo?: number;
  publicationType?: string;
  language?: string;
  sortBy?: "relevance" | "year" | "citations" | "title";
  sortOrder?: "asc" | "desc";
};

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
  filters: SourceSearchFilters = {},
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
          limit: 20,
          year: filters.year,
          open_access: filters.openAccess ?? false,
          min_citations: filters.minCitations,
          max_citations: filters.maxCitations,
          author: filters.author,
          venue: filters.venue,
          year_from: filters.yearFrom,
          year_to: filters.yearTo,
          publication_type: filters.publicationType,
          language: filters.language,
          sort_by: filters.sortBy ?? "relevance",
          sort_order: filters.sortOrder ?? "desc",
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