"use client";

import { useEffect, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function LiteraturePage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [projectId, setProjectId] = useState("");

  const projects = useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.projects(workspaceId!),
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (!projectId && projects.data?.items[0]?.id) {
      setProjectId(projects.data.items[0].id);
    }
  }, [projects.data, projectId]);

  const literature = useQuery({
    queryKey: ["literature", projectId],
    queryFn: () => api.literature(projectId),
    enabled: !!projectId,
  });

  const clusters = useQuery({
    queryKey: ["literature-clusters", projectId],
    queryFn: () => api.literatureClusters(projectId),
    enabled: !!projectId,
  });

  const gaps = useQuery({
    queryKey: ["literature-gaps", projectId],
    queryFn: () => api.literatureGaps(projectId),
    enabled: !!projectId,
  });

  const runs = useQuery({
    queryKey: ["literature-runs", projectId],
    queryFn: () => api.literatureRuns(projectId),
    enabled: !!projectId,
  });

  const analyze = useMutation({
    mutationFn: () => api.analyzeLiterature(projectId, false),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["literature", projectId],
      });
      queryClient.invalidateQueries({
        queryKey: ["literature-clusters", projectId],
      });
      queryClient.invalidateQueries({
        queryKey: ["literature-gaps", projectId],
      });
      queryClient.invalidateQueries({
        queryKey: ["literature-runs", projectId],
      });
    },
  });

  const screen = useMutation({
    mutationFn: ({
      itemId,
      status,
    }: {
      itemId: string;
      status:
        | "discovered"
        | "candidate"
        | "included"
        | "excluded"
        | "uncertain";
    }) =>
      api.updateLiteratureScreening(
        projectId,
        itemId,
        status,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["literature", projectId],
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
          Literature intelligence
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Literature
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Literature corpus, screening decisions,
          clustering, gaps, and analysis runs come
          directly from the project intelligence APIs.
        </p>
      </header>

      <section className="card p-5">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <h2 className="font-semibold">
              Project
            </h2>

            <select
              className="input mt-3 min-w-72"
              value={projectId}
              onChange={(event) =>
                setProjectId(event.target.value)
              }
            >
              {(projects.data?.items ?? []).map(
                (project) => (
                  <option
                    key={project.id}
                    value={project.id}
                  >
                    {project.name}
                  </option>
                ),
              )}
            </select>
          </div>

          <button
            className="btn btn-primary self-end"
            disabled={
              !projectId || analyze.isPending
            }
            onClick={() => analyze.mutate()}
          >
            {analyze.isPending
              ? "Analyzing…"
              : "Run literature analysis"}
          </button>
        </div>

        {analyze.data && (
          <div className="muted text-sm mt-4">
            Analysis status:{" "}
            {analyze.data.status}
            {analyze.data.job_id
              ? " · job " +
                analyze.data.job_id
              : ""}
          </div>
        )}

        {analyze.error && (
          <div
            className="text-sm mt-3"
            style={{ color: "var(--danger)" }}
          >
            {analyze.error.message}
          </div>
        )}
      </section>

      <div className="grid md:grid-cols-4 gap-4">
        <Metric
          label="Papers"
          value={
            literature.data?.total ?? "—"
          }
        />

        <Metric
          label="Clusters"
          value={
            clusters.data?.total ?? "—"
          }
        />

        <Metric
          label="Gaps"
          value={
            gaps.data?.total ?? "—"
          }
        />

        <Metric
          label="Runs"
          value={
            runs.data?.total ?? "—"
          }
        />
      </div>

      <section className="card overflow-hidden">
        <div className="px-5 py-4 border-b">
          <div className="font-semibold">
            Literature corpus
          </div>
          <div className="muted text-xs mt-1">
            Screening decisions are persisted on the backend.
          </div>
        </div>

        <div className="divide-y">
          {(literature.data?.items ?? []).map(
            (item) => (
              <div
                key={item.id}
                className="px-5 py-4"
              >
                <div className="flex justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-medium">
                      Source {item.source_id}
                    </div>

                    <div className="muted text-sm mt-1">
                      {item.paper_type_code ??
                        "Paper type unknown"}{" "}
                      ·{" "}
                      {item.research_design_code ??
                        "Design unknown"}
                    </div>

                    {item.relevance_score !=
                      null && (
                      <div className="muted text-xs mt-2">
                        Relevance:{" "}
                        {item.relevance_score.toFixed(
                          2,
                        )}
                        {item.relevance_confidence !=
                          null
                          ? " · confidence " +
                            item.relevance_confidence.toFixed(
                              2,
                            )
                          : ""}
                      </div>
                    )}

                    {item.study_summary && (
                      <p className="muted text-sm mt-3 line-clamp-3">
                        {item.study_summary}
                      </p>
                    )}
                  </div>

                  <select
                    className="input !w-auto h-fit text-sm"
                    value={
                      item.screening_status
                    }
                    onChange={(event) =>
                      screen.mutate({
                        itemId: item.id,
                        status:
                          event.target.value as
                            | "discovered"
                            | "candidate"
                            | "included"
                            | "excluded"
                            | "uncertain",
                      })
                    }
                  >
                    <option value="discovered">
                      discovered
                    </option>
                    <option value="candidate">
                      candidate
                    </option>
                    <option value="included">
                      included
                    </option>
                    <option value="excluded">
                      excluded
                    </option>
                    <option value="uncertain">
                      uncertain
                    </option>
                  </select>
                </div>
              </div>
            ),
          )}

          {literature.isPending && (
            <div className="p-6 muted">
              Loading literature…
            </div>
          )}

          {!literature.isPending &&
            !literature.data?.items.length && (
              <div className="p-8 muted text-sm">
                No literature items are available
                for this project yet.
              </div>
            )}
        </div>
      </section>

      <div className="grid lg:grid-cols-2 gap-5">
        <section className="card p-5">
          <h2 className="font-semibold">
            Clusters
          </h2>

          <div className="mt-4 space-y-3">
            {(clusters.data?.items ?? []).map(
              (cluster) => (
                <div
                  key={cluster.id}
                  className="rounded-xl border p-4"
                  style={{
                    borderColor: "var(--line)",
                  }}
                >
                  <div className="font-medium">
                    {cluster.name}
                  </div>

                  <div className="muted text-sm mt-1">
                    {cluster.source_count} sources ·{" "}
                    {cluster.evidence_strength !=
                    null
                      ? "strength " +
                        cluster.evidence_strength.toFixed(
                          2,
                        )
                      : "strength unavailable"}
                  </div>

                  {cluster.summary && (
                    <p className="muted text-sm mt-3">
                      {cluster.summary}
                    </p>
                  )}
                </div>
              ),
            )}

            {!clusters.data?.items.length && (
              <div className="muted text-sm">
                No clusters reported.
              </div>
            )}
          </div>
        </section>

        <section className="card p-5">
          <h2 className="font-semibold">
            Research gaps
          </h2>

          <div className="mt-4 space-y-3">
            {(gaps.data?.items ?? []).map(
              (gap) => (
                <div
                  key={gap.id}
                  className="rounded-xl border p-4"
                  style={{
                    borderColor: "var(--line)",
                  }}
                >
                  <div className="font-medium">
                    {gap.title}
                  </div>

                  <div className="muted text-xs mt-1">
                    {gap.gap_type} · confidence{" "}
                    {gap.confidence.toFixed(2)}
                  </div>

                  <p className="muted text-sm mt-3">
                    {gap.description}
                  </p>
                </div>
              ),
            )}

            {!gaps.data?.items.length && (
              <div className="muted text-sm">
                No research gaps reported.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="card p-5">
      <div className="muted text-sm">
        {label}
      </div>
      <div className="text-2xl font-semibold mt-2">
        {value}
      </div>
    </div>
  );
}