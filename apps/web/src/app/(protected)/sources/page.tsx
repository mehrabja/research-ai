"use client";

import { useEffect, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function SourcesPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [projectId, setProjectId] = useState("");
  const [reportId, setReportId] = useState("");
  const [query, setQuery] = useState("");

  const projects = useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.projects(workspaceId!),
    enabled: !!workspaceId,
  });

  useEffect(() => {
    const first = projects.data?.items[0]?.id;

    if (!projectId && first) {
      setProjectId(first);
    }
  }, [projects.data, projectId]);

  const reports = useQuery({
    queryKey: ["project-reports", projectId, workspaceId],
    queryFn: () =>
      api.projectReports(
        projectId,
        workspaceId!,
      ),
    enabled:
      !!workspaceId &&
      !!projectId,
  });

  useEffect(() => {
    const first = reports.data?.items[0]?.id;

    if (first && !reportId) {
      setReportId(first);
    }

    if (
      reportId &&
      reports.data &&
      !reports.data.items.some(
        (item) => item.id === reportId,
      )
    ) {
      setReportId(first ?? "");
    }
  }, [reports.data, reportId]);

  const sources = useQuery({
    queryKey: ["sources", reportId],
    queryFn: () => api.sources(reportId),
    enabled: !!reportId,
  });

  const search = useMutation({
    mutationFn: () =>
      api.searchSources(
        reportId,
        query,
        {
          limit: 8,
          sort_by: "relevance",
          sort_order: "desc",
        },
      ),
  });

  const add = useMutation({
    mutationFn: (
      candidate: Parameters<
        typeof api.createSource
      >[1],
    ) =>
      api.createSource(
        reportId,
        candidate,
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["sources", reportId],
      });
    },
  });

  const extract = useMutation({
    mutationFn: (sourceId: string) =>
      api.extractSource(
        reportId,
        sourceId,
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["sources", reportId],
      });
    },
  });

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Evidence discovery
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Sources
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Discover external sources, register them
          against a report, and run source extraction
          through the backend pipeline.
        </p>
      </header>

      <section className="card p-5">
        <h2 className="font-semibold">
          Report context
        </h2>

        <div className="grid md:grid-cols-2 gap-4 mt-4">
          <label>
            <div className="muted text-sm">
              Project
            </div>

            <select
              className="input mt-2"
              value={projectId}
              onChange={(event) => {
                setProjectId(
                  event.target.value,
                );
                setReportId("");
              }}
            >
              {(projects.data?.items ?? []).map(
                (item) => (
                  <option
                    key={item.id}
                    value={item.id}
                  >
                    {item.name}
                  </option>
                ),
              )}
            </select>
          </label>

          <label>
            <div className="muted text-sm">
              Report
            </div>

            <select
              className="input mt-2"
              value={reportId}
              onChange={(event) =>
                setReportId(
                  event.target.value,
                )
              }
              disabled={
                reports.isPending ||
                !reports.data?.items.length
              }
            >
              {(reports.data?.items ?? []).map(
                (item) => (
                  <option
                    key={item.id}
                    value={item.id}
                  >
                    {item.topic}
                  </option>
                ),
              )}
            </select>
          </label>
        </div>

        {!reports.isPending &&
          !reports.data?.items.length && (
            <div className="muted text-sm mt-4">
              This project has no reports yet.
            </div>
          )}
      </section>

      {reportId && (
        <>
          <section className="card p-5">
            <h2 className="font-semibold">
              Discover sources
            </h2>

            <div className="mt-4 flex gap-2">
              <input
                className="input"
                placeholder="Search papers, authors, topics…"
                value={query}
                onChange={(event) =>
                  setQuery(
                    event.target.value,
                  )
                }
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    query.trim() &&
                    !search.isPending
                  ) {
                    search.mutate();
                  }
                }}
              />

              <button
                className="btn btn-primary"
                disabled={
                  !query.trim() ||
                  search.isPending
                }
                onClick={() =>
                  search.mutate()
                }
              >
                {search.isPending
                  ? "Searching…"
                  : "Search"}
              </button>
            </div>

            {search.error && (
              <div
                className="text-sm mt-3"
                style={{
                  color: "var(--danger)",
                }}
              >
                {search.error.message}
              </div>
            )}

            <div className="mt-5 space-y-3">
              {(search.data?.candidates ?? []).map(
                (candidate, index) => (
                  <div
                    key={
                      candidate.external_source_id +
                      "-" +
                      index
                    }
                    className="rounded-xl border p-4"
                    style={{
                      borderColor:
                        "var(--line)",
                    }}
                  >
                    <div className="flex justify-between gap-4">
                      <div className="min-w-0">
                        <div className="font-medium">
                          {candidate.title}
                        </div>

                        <div className="muted text-sm mt-1">
                          {candidate.authors
                            ?.slice(0, 4)
                            .join(", ") ||
                            "Authors unavailable"}

                          {candidate.year
                            ? " · " +
                              candidate.year
                            : ""}

                          {candidate.citation_count !=
                            null
                            ? " · " +
                              candidate.citation_count +
                              " citations"
                            : ""}
                        </div>

                        {candidate.url && (
                          <a
                            href={
                              candidate.url
                            }
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs underline mt-2 inline-block"
                          >
                            Open source
                          </a>
                        )}
                      </div>

                      <button
                        className="btn btn-secondary text-sm shrink-0"
                        disabled={
                          add.isPending
                        }
                        onClick={() =>
                          add.mutate(
                            candidate,
                          )
                        }
                      >
                        Add
                      </button>
                    </div>

                    {candidate.abstract && (
                      <p className="muted text-sm mt-3 line-clamp-4">
                        {candidate.abstract}
                      </p>
                    )}
                  </div>
                ),
              )}

              {!search.isPending &&
                search.data &&
                search.data.candidates
                  .length === 0 && (
                  <div className="muted text-sm">
                    No candidates found.
                  </div>
                )}
            </div>
          </section>

          <section className="card overflow-hidden">
            <div className="px-5 py-4 border-b flex items-center justify-between gap-4">
              <div>
                <div className="font-semibold">
                  Registered sources
                </div>
                <div className="muted text-xs mt-1">
                  {sources.data?.items.length ??
                    0}{" "}
                  sources
                </div>
              </div>
            </div>

            <div className="divide-y">
              {(sources.data?.items ?? []).map(
                (source) => (
                  <div
                    key={source.id}
                    className="px-5 py-4"
                  >
                    <div className="flex justify-between gap-4">
                      <div className="min-w-0">
                        <div className="font-medium">
                          {source.title}
                        </div>

                        <div className="muted text-sm mt-1">
                          {source.authors
                            ?.slice(0, 4)
                            .join(", ") ||
                            "Authors unavailable"}

                          {source.year
                            ? " · " +
                              source.year
                            : ""}
                        </div>

                        <div className="muted text-xs mt-2">
                          status:{" "}
                          {source.status}
                        </div>
                      </div>

                      <button
                        className="btn btn-secondary text-xs shrink-0"
                        disabled={
                          extract.isPending
                        }
                        onClick={() =>
                          extract.mutate(
                            source.id,
                          )
                        }
                      >
                        {extract.isPending &&
                        extract.variables ===
                          source.id
                          ? "Extracting…"
                          : "Extract"}
                      </button>
                    </div>

                    {source.doi && (
                      <div className="muted text-xs mt-2">
                        DOI: {source.doi}
                      </div>
                    )}
                  </div>
                ),
              )}

              {sources.isPending && (
                <div className="p-6 muted text-sm">
                  Loading sources…
                </div>
              )}

              {!sources.isPending &&
                sources.data?.items.length ===
                  0 && (
                  <div className="p-8 muted text-sm">
                    No sources registered for
                    this report yet.
                  </div>
                )}
            </div>

            {extract.data && (
              <div className="border-t p-5">
                <div className="font-medium">
                  Latest extraction
                </div>

                <div className="grid md:grid-cols-3 gap-3 mt-3 text-sm">
                  <div>
                    <div className="muted">
                      Status
                    </div>
                    <div className="mt-1">
                      {extract.data.status}
                    </div>
                  </div>

                  <div>
                    <div className="muted">
                      Chunks
                    </div>
                    <div className="mt-1">
                      {extract.data.chunk_count}
                    </div>
                  </div>

                  <div>
                    <div className="muted">
                      Content type
                    </div>
                    <div className="mt-1">
                      {extract.data
                        .content_type ??
                        "—"}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}