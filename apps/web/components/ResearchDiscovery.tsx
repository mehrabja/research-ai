"use client";

import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Link from "next/link";
import {
  createResearchReport,
  saveSource,
  searchSources,
  type SourceCandidate,
  type SourceSearchFilters,
} from "@/lib/api/research";
import { useResearchContext } from "@/lib/research-context";

const DEFAULT_QUERY =
  "transformer-based neural decoding of sparse fMRI under low-data conditions";

type FilterState = {
  year: string;
  yearFrom: string;
  yearTo: string;
  minCitations: string;
  maxCitations: string;
  author: string;
  venue: string;
  publicationType: string;
  language: string;
  openAccess: boolean;
  sortBy: NonNullable<SourceSearchFilters["sortBy"]>;
  sortOrder: NonNullable<SourceSearchFilters["sortOrder"]>;
};

const DEFAULT_FILTERS: FilterState = {
  year: "",
  yearFrom: "",
  yearTo: "",
  minCitations: "",
  maxCitations: "",
  author: "",
  venue: "",
  publicationType: "",
  language: "",
  openAccess: false,
  sortBy: "relevance",
  sortOrder: "desc",
};

export default function ResearchDiscovery() {
  const {
    projectId,
    reportId,
    reportsQuery,
    setReport,
    contextHref,
  } = useResearchContext();

  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [resultsState, setResultsState] = useState<{
    key: string;
    reportId: string | null;
    results: SourceCandidate[];
    savedKeys: Set<string>;
  }>({
    key: "",
    reportId: null,
    results: [],
    savedKeys: new Set(),
  });

  const contextKey = projectId ?? "";
  const sameContext = resultsState.key === contextKey;
  const results = useMemo(
    () => (sameContext ? resultsState.results : []),
    [resultsState.results, sameContext],
  );
  const savedKeys = sameContext
    ? resultsState.savedKeys
    : new Set<string>();
  const activeReportId =
    reportId ?? (sameContext ? resultsState.reportId : null);

  const providerLabels = useMemo(() => {
    const providers = new Set<string>();
    for (const candidate of results) {
      const federated = candidate.source_meta?.federated;
      if (federated && typeof federated === "object") {
        const rawProviders =
          (federated as { providers?: unknown }).providers;
        if (Array.isArray(rawProviders)) {
          for (const value of rawProviders) {
            if (typeof value === "string" && value.trim()) {
              providers.add(value);
            }
          }
        }
      }
      if (providers.size === 0 && candidate.source_api) {
        providers.add(candidate.source_api);
      }
    }
    return [...providers].sort();
  }, [results]);

  function buildFilters(): SourceSearchFilters {
    const numberOrUndefined = (value: string) => {
      const trimmed = value.trim();
      if (!trimmed) return undefined;
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : undefined;
    };

    return {
      year: numberOrUndefined(filters.year),
      yearFrom: numberOrUndefined(filters.yearFrom),
      yearTo: numberOrUndefined(filters.yearTo),
      minCitations: numberOrUndefined(filters.minCitations),
      maxCitations: numberOrUndefined(filters.maxCitations),
      author: filters.author.trim() || undefined,
      venue: filters.venue.trim() || undefined,
      publicationType: filters.publicationType.trim() || undefined,
      language: filters.language.trim() || undefined,
      openAccess: filters.openAccess,
      sortBy: filters.sortBy,
      sortOrder: filters.sortOrder,
    };
  }

  const createReport = useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error(
          "Select a research project before creating a report.",
        );
      }
      return createResearchReport(query.trim(), projectId);
    },
    onSuccess: async (report) => {
      const refreshed = await reportsQuery.refetch();
      if (refreshed.data?.some((item) => item.id === report.id)) {
        setReport(report.id);
      }
    },
  });

  const discovery = useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error(
          "Select a research project before running discovery.",
        );
      }

      let activeId = activeReportId;

      if (!activeId) {
        const report = await createResearchReport(query.trim(), projectId);
        const refreshed = await reportsQuery.refetch();
        activeId = report.id;
        if (refreshed.data?.some((item) => item.id === report.id)) {
          setReport(report.id);
        }
      }

      return {
        reportId: activeId,
        candidates: await searchSources(
          activeId,
          query.trim(),
          buildFilters(),
        ),
      };
    },
    onSuccess: ({ reportId: discoveredReportId, candidates }) =>
      setResultsState({
        key: contextKey,
        reportId: discoveredReportId,
        results: candidates,
        savedKeys: new Set(),
      }),
  });

  const save = useMutation({
    mutationFn: (candidate: SourceCandidate) => {
      if (!activeReportId) {
        throw new Error(
          "Create or select a research report before saving sources.",
        );
      }
      return saveSource(activeReportId, candidate);
    },
    onSuccess: async (_source, candidate) => {
      setResultsState((current) => {
        const next =
          current.key === contextKey
            ? new Set(current.savedKeys)
            : new Set<string>();
        next.add(sourceKey(candidate));
        return {
          key: contextKey,
          reportId: activeReportId,
          results: current.key === contextKey ? current.results : [],
          savedKeys: next,
        };
      });
    },
  });

  const busy =
    reportsQuery.isPending ||
    discovery.isPending ||
    createReport.isPending ||
    save.isPending;

  if (!projectId) {
    return (
      <section className="card pad empty">
        <div className="big">∅</div>
        <h2>Select a research project</h2>
        <p className="muted">
          Discovery is project-scoped. Select a project from the
          context switcher above to continue.
        </p>
        <Link
          className="btn primary"
          style={{ marginTop: 14 }}
          href={contextHref("/workspace")}
        >
          Open workspace
        </Link>
      </section>
    );
  }

  return (
    <>
      <div className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">
              Project: {projectId.slice(0, 8)}…
            </div>
            <h2>Literature discovery</h2>
            <p className="muted small">
              Federated source discovery runs inside the active
              research project and report.
            </p>
          </div>
          <span className="tag">Project scoped</span>
          {activeReportId && (
            <span className="tag success">Report selected</span>
          )}
        </div>

        <div className="field" style={{ marginTop: 14 }}>
          <label htmlFor="research-question">Research question</label>
          <input
            id="research-question"
            className="input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <details style={{ marginTop: 14 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            Advanced discovery filters
          </summary>
          <div className="grid grid-3" style={{ marginTop: 12 }}>
            <div className="field">
              <label htmlFor="filter-year">Exact year</label>
              <input
                id="filter-year"
                className="input"
                inputMode="numeric"
                value={filters.year}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    year: event.target.value,
                  }))
                }
                placeholder="2024"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-year-from">Year from</label>
              <input
                id="filter-year-from"
                className="input"
                inputMode="numeric"
                value={filters.yearFrom}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    yearFrom: event.target.value,
                  }))
                }
                placeholder="2020"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-year-to">Year to</label>
              <input
                id="filter-year-to"
                className="input"
                inputMode="numeric"
                value={filters.yearTo}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    yearTo: event.target.value,
                  }))
                }
                placeholder="2026"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-min-citations">Min citations</label>
              <input
                id="filter-min-citations"
                className="input"
                inputMode="numeric"
                value={filters.minCitations}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    minCitations: event.target.value,
                  }))
                }
                placeholder="10"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-max-citations">Max citations</label>
              <input
                id="filter-max-citations"
                className="input"
                inputMode="numeric"
                value={filters.maxCitations}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    maxCitations: event.target.value,
                  }))
                }
                placeholder="1000"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-author">Author</label>
              <input
                id="filter-author"
                className="input"
                value={filters.author}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    author: event.target.value,
                  }))
                }
                placeholder="Author name"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-venue">Venue / journal</label>
              <input
                id="filter-venue"
                className="input"
                value={filters.venue}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    venue: event.target.value,
                  }))
                }
                placeholder="NeurIPS"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-publication-type">
                Publication type
              </label>
              <input
                id="filter-publication-type"
                className="input"
                value={filters.publicationType}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    publicationType: event.target.value,
                  }))
                }
                placeholder="journal-article"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-language">Language</label>
              <input
                id="filter-language"
                className="input"
                value={filters.language}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    language: event.target.value,
                  }))
                }
                placeholder="en"
              />
            </div>
            <label className="list-item row" style={{ cursor: "pointer" }}>
              <span>
                <strong>Open access only</strong>
                <span className="muted small" style={{ display: "block" }}>
                  Keep only sources marked open access.
                </span>
              </span>
              <input
                type="checkbox"
                aria-label="Open access only"
                checked={filters.openAccess}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    openAccess: event.target.checked,
                  }))
                }
              />
            </label>
            <div className="field">
              <label htmlFor="filter-sort-by">Sort by</label>
              <select
                id="filter-sort-by"
                className="input"
                value={filters.sortBy}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    sortBy: event.target.value as FilterState["sortBy"],
                  }))
                }
              >
                <option value="relevance">Relevance</option>
                <option value="year">Year</option>
                <option value="citations">Citations</option>
                <option value="title">Title</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="filter-sort-order">Sort order</label>
              <select
                id="filter-sort-order"
                className="input"
                value={filters.sortOrder}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    sortOrder: event.target.value as FilterState["sortOrder"],
                  }))
                }
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>
            <button
              className="btn"
              type="button"
              style={{ alignSelf: "end" }}
              onClick={() => setFilters(DEFAULT_FILTERS)}
            >
              Reset filters
            </button>
          </div>
        </details>

        <div className="actions" style={{ marginTop: 12 }}>
          {!activeReportId && (
            <button
              className="btn"
              type="button"
              disabled={busy || query.trim().length < 3}
              onClick={() => createReport.mutate()}
            >
              Create research report
            </button>
          )}

          <button
            className="btn primary"
            type="button"
            disabled={busy || query.trim().length < 3}
            onClick={() => discovery.mutate()}
          >
            {discovery.isPending ? "Searching…" : "Run discovery →"}
          </button>
        </div>

        {providerLabels.length > 0 && (
          <div className="pillbar" style={{ marginTop: 12 }}>
            {providerLabels.map((provider) => (
              <span className="tag" key={provider}>
                {provider}
              </span>
            ))}
            <span className="tag success">
              {results.length} live results
            </span>
          </div>
        )}
      </div>

      {(reportsQuery.error ||
        createReport.error ||
        discovery.error ||
        save.error) && (
        <div className="card pad" style={{ marginTop: 16 }} role="alert">
          <p className="muted">
            {reportsQuery.error?.message ??
              createReport.error?.message ??
              discovery.error?.message ??
              save.error?.message}
          </p>
        </div>
      )}

      {results.length > 0 && (
        <div className="card pad" style={{ marginTop: 16 }}>
          <div className="row">
            <div>
              <h3>Live results</h3>
              <div className="muted small">
                {results.length} candidates from the federated discovery API
              </div>
            </div>
            <span className="tag success">Live</span>
          </div>

          <div className="list" style={{ marginTop: 10 }}>
            {results.map((candidate) => {
              const key = sourceKey(candidate);
              const saved = savedKeys.has(key);

              return (
                <article className="list-item" key={key}>
                  <div className="row">
                    <div style={{ minWidth: 0 }}>
                      <div className="title">{candidate.title}</div>
                      <div className="meta">
                        {candidate.year ?? "Year n/a"} ·{" "}
                        {candidate.citation_count ?? 0} citations ·{" "}
                        {candidate.source_api}
                      </div>
                    </div>
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={saved || save.isPending}
                      onClick={() => save.mutate(candidate)}
                    >
                      {saved ? "Saved" : "Save"}
                    </button>
                  </div>

                  {candidate.authors?.length ? (
                    <p className="muted small" style={{ marginTop: 7 }}>
                      {candidate.authors.slice(0, 5).join(", ")}
                    </p>
                  ) : null}

                  {candidate.abstract && (
                    <p className="muted small" style={{ marginTop: 7 }}>
                      {candidate.abstract.slice(0, 320)}
                      {candidate.abstract.length > 320 ? "…" : ""}
                    </p>
                  )}

                  <div className="pillbar" style={{ marginTop: 8 }}>
                    {candidate.doi && (
                      <span className="tag">DOI {candidate.doi}</span>
                    )}
                    {candidate.source_meta?.is_open_access === true && (
                      <span className="tag success">Open access</span>
                    )}
                    {providerNames(candidate).map((provider) => (
                      <span className="tag" key={provider}>
                        {provider}
                      </span>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}

      {!discovery.isPending &&
        discovery.isSuccess &&
        results.length === 0 && (
          <div className="card pad empty" style={{ marginTop: 16 }}>
            <div className="big">∅</div>
            <div>No sources matched this query and filter set.</div>
          </div>
        )}
    </>
  );
}

function providerNames(candidate: SourceCandidate): string[] {
  const value = candidate.source_meta?.federated;
  if (!value || typeof value !== "object") {
    return [candidate.source_api];
  }
  const providers = (value as { providers?: unknown }).providers;
  if (!Array.isArray(providers)) {
    return [candidate.source_api];
  }
  const names = providers.filter(
    (provider): provider is string =>
      typeof provider === "string" && provider.trim().length > 0,
  );
  return names.length ? names : [candidate.source_api];
}

function sourceKey(candidate: SourceCandidate): string {
  return candidate.source_api + ":" + candidate.external_source_id;
}
