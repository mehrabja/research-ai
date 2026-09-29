"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useResearchContext } from "@/lib/research-context";
import {
  analyzeLiterature,
  listLiterature,
  listLiteratureClusters,
  listLiteratureGaps,
  updateLiteratureScreening,
  type LiteratureItem,
} from "@/lib/api/literature";

const SCREENING_OPTIONS = [
  "all",
  "discovered",
  "candidate",
  "included",
  "excluded",
  "uncertain",
] as const;

export default function LiteratureMap() {
  const [screening, setScreening] =
    useState<(typeof SCREENING_OPTIONS)[number]>("all");

  const {
    workspaceId: activeWorkspaceId,
    projectId: activeProjectId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
    setWorkspace: setWorkspaceId,
    setProject: setProjectId,
  } = useResearchContext();

  const literature = useQuery({
    queryKey: ["literature", activeProjectId, screening],
    queryFn: () =>
      listLiterature(
        activeProjectId!,
        screening === "all" ? undefined : screening,
      ),
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const clusters = useQuery({
    queryKey: ["literature-clusters", activeProjectId],
    queryFn: () => listLiteratureClusters(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });

  const gaps = useQuery({
    queryKey: ["literature-gaps", activeProjectId],
    queryFn: () => listLiteratureGaps(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });

  const analyze = useMutation({
    mutationFn: () => analyzeLiterature(activeProjectId!, false),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["literature"] }),
        queryClient.invalidateQueries({
          queryKey: ["literature-clusters", activeProjectId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["literature-gaps", activeProjectId],
        }),
      ]);
    },
  });

  const screeningMutation = useMutation({
    mutationFn: ({
      item,
      status,
    }: {
      item: LiteratureItem;
      status: LiteratureItem["screening_status"];
    }) =>
      updateLiteratureScreening(
        activeProjectId!,
        item.id,
        status as
          | "discovered"
          | "candidate"
          | "included"
          | "excluded"
          | "uncertain",
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["literature"],
      });
    },
  });

  const items = literature.data?.items ?? [];
  const includedCount = items.filter(
    (item) => item.screening_status === "included",
  ).length;
  const candidateCount = items.filter(
    (item) => item.screening_status === "candidate",
  ).length;

  const analysisErrors = useMemo(
    () =>
      [
        workspaces.error,
        projects.error,
        literature.error,
        clusters.error,
        gaps.error,
        analyze.error,
        screeningMutation.error,
      ].filter(Boolean),
    [
      workspaces.error,
      projects.error,
      literature.error,
      clusters.error,
      gaps.error,
      analyze.error,
      screeningMutation.error,
    ],
  );

  if (analysisErrors.length > 0) {
    const error = analysisErrors[0] as Error;
    return (
      <section className="card pad" role="alert">
        <h2>Literature unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {error.message}
        </p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 14 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void literature.refetch();
            void clusters.refetch();
            void gaps.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  const hasProject = Boolean(activeProjectId);

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Project intelligence</div>
            <h2 style={{ marginTop: 4 }}>Literature corpus</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Literature records, screening decisions, clusters and gaps from
              the selected project.
            </p>
          </div>
          <button
            className="btn primary"
            type="button"
            disabled={!hasProject || analyze.isPending}
            onClick={() => analyze.mutate()}
          >
            {analyze.isPending ? "Analyzing…" : "Analyze corpus"}
          </button>
        </div>

        {!hasProject && !projects.isPending && (
          <div className="empty" style={{ marginTop: 14 }}>
            <div className="big">∅</div>
            <div>
              Create a project in Workspace before analyzing literature.
            </div>
          </div>
        )}
      </section>

      <section className="grid grid-4">
        <div className="card metric">
          <div className="label">Papers</div>
          <div className="value">{literature.data?.total ?? 0}</div>
          <div className="delta">Current project corpus</div>
        </div>
        <div className="card metric">
          <div className="label">Candidates</div>
          <div className="value">{candidateCount}</div>
          <div className="delta">Screening queue</div>
        </div>
        <div className="card metric">
          <div className="label">Included</div>
          <div className="value">{includedCount}</div>
          <div className="delta">Manual screening state</div>
        </div>
        <div className="card metric">
          <div className="label">Gaps</div>
          <div className="value">{gaps.data?.length ?? 0}</div>
          <div className="delta">Backend gap analysis</div>
        </div>
      </section>

      <section className="card pad">
        <div className="row">
          <div>
            <h2>Screening</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Screening state is persisted through the literature API.
            </p>
          </div>
          <select
            id="literature-screening-filter"
            className="input"
            style={{ maxWidth: 190 }}
            value={screening}
            onChange={(event) =>
              setScreening(
                event.target.value as (typeof SCREENING_OPTIONS)[number],
              )
            }
            aria-label="Screening filter"
          >
            {SCREENING_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "All statuses" : option}
              </option>
            ))}
          </select>
        </div>

        <div className="list" style={{ marginTop: 12 }}>
          {items.map((item) => (
            <article className="list-item" key={item.id}>
              <div className="row">
                <div style={{ minWidth: 0 }}>
                  <div className="title">
                    Source {item.source_id.slice(0, 8)}…
                  </div>
                  <div className="meta">
                    {item.paper_type_code ?? "Type n/a"} ·{" "}
                    {item.research_design_code ?? "Design n/a"} · analysis{" "}
                    {item.analysis_status}
                  </div>
                </div>

                <select
                  className="input"
                  style={{ maxWidth: 150 }}
                  value={item.screening_status}
                  aria-label={"Screening status for " + item.id}
                  disabled={
                    screeningMutation.isPending ||
                    !activeProjectId
                  }
                  onChange={(event) =>
                    screeningMutation.mutate({
                      item,
                      status: event.target.value,
                    })
                  }
                >
                  {SCREENING_OPTIONS.filter(
                    (option) => option !== "all",
                  ).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>

              {item.relevance_reason && (
                <p className="muted small" style={{ marginTop: 7 }}>
                  {item.relevance_reason}
                </p>
              )}

              {(item.themes?.length ?? 0) > 0 && (
                <div className="pillbar" style={{ marginTop: 8 }}>
                  {item.themes?.slice(0, 5).map((theme) => (
                    <span className="tag" key={theme}>
                      {theme}
                    </span>
                  ))}
                </div>
              )}
            </article>
          ))}

          {!literature.isPending && items.length === 0 && (
            <div className="empty">
              <div className="big">∅</div>
              <div>
                No literature items exist for this project yet. Save sources
                through Research discovery, then analyze the corpus.
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card pad">
          <div className="row">
            <h2>Clusters</h2>
            <span className="tag">{clusters.data?.length ?? 0}</span>
          </div>

          <div className="list" style={{ marginTop: 12 }}>
            {(clusters.data ?? []).map((cluster) => (
              <article className="list-item" key={cluster.id}>
                <div className="title">{cluster.name}</div>
                <div className="meta">
                  {cluster.source_count} sources ·{" "}
                  {cluster.cluster_method} · {cluster.status}
                </div>
                {cluster.summary && (
                  <p className="muted small" style={{ marginTop: 6 }}>
                    {cluster.summary}
                  </p>
                )}
              </article>
            ))}

            {!clusters.isPending && (clusters.data?.length ?? 0) === 0 && (
              <div className="empty">
                <div className="big">∅</div>
                <div>No clusters have been generated yet.</div>
              </div>
            )}
          </div>
        </div>

        <div className="card pad">
          <div className="row">
            <h2>Evidence gaps</h2>
            <span className="tag">{gaps.data?.length ?? 0}</span>
          </div>

          <div className="list" style={{ marginTop: 12 }}>
            {(gaps.data ?? []).map((gap) => (
              <article className="list-item" key={gap.id}>
                <div className="row">
                  <div className="title">{gap.title}</div>
                  <span className="tag">{Math.round(gap.confidence * 100)}%</span>
                </div>
                <div className="meta">
                  {gap.gap_type} · {gap.status}
                </div>
                <p className="muted small" style={{ marginTop: 6 }}>
                  {gap.description}
                </p>
              </article>
            ))}

            {!gaps.isPending && (gaps.data?.length ?? 0) === 0 && (
              <div className="empty">
                <div className="big">∅</div>
                <div>No evidence gaps have been generated yet.</div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
