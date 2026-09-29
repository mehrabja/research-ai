"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useResearchContext } from "@/lib/research-context";
import {
  generateKnowledgeGraph,
  getKnowledgeGraph,
  getKnowledgeGraphSummary,
  knowledgeGraphExportUrl,
} from "@/lib/api/knowledgeGraph";

export default function KnowledgeGraphView() {
  const queryClient = useQueryClient();
  const {
    projectId: activeProjectId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
  } = useResearchContext();

  const graph = useQuery({
    queryKey: ["knowledge-graph", activeProjectId],
    queryFn: () => getKnowledgeGraph(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const summary = useQuery({
    queryKey: ["knowledge-graph-summary", activeProjectId],
    queryFn: () => getKnowledgeGraphSummary(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const generate = useMutation({
    mutationFn: () => generateKnowledgeGraph(activeProjectId!, false),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["knowledge-graph", activeProjectId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["knowledge-graph-summary", activeProjectId],
      });
    },
  });

  const errors = [
    workspaces.error,
    projects.error,
    graph.error,
    summary.error,
    generate.error,
  ].filter(Boolean);

  if (errors.length) {
    return (
      <section className="card pad" role="alert">
        <h2>Knowledge graph unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {(errors[0] as Error).message}
        </p>
        <button
          className="btn"
          style={{ marginTop: 14 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void graph.refetch();
            void summary.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  const hasGraph = Boolean(graph.data || summary.data);
  const nodeTypes = Object.entries(summary.data?.node_type_counts ?? {});
  const relationTypes = Object.entries(
    summary.data?.relation_type_counts ?? {},
  );

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Project knowledge</div>
            <h2 style={{ marginTop: 4 }}>Knowledge graph</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Graph metadata and aggregate topology from the project graph
              service. No synthetic nodes are rendered.
            </p>
          </div>
          <div className="actions">
            <button
              className="btn primary"
              disabled={!activeProjectId || generate.isPending}
              onClick={() => generate.mutate()}
            >
              {generate.isPending ? "Generating…" : hasGraph ? "Regenerate" : "Generate graph"}
            </button>
            {hasGraph && activeProjectId && (
              <a
                className="btn"
                href={knowledgeGraphExportUrl(activeProjectId)}
              >
                Export JSON
              </a>
            )}
          </div>
        </div>

      </section>

      {!activeProjectId && !projects.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>Create a project in Workspace before generating a knowledge graph.</div>
        </section>
      )}

      {activeProjectId && !hasGraph && !summary.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>No knowledge graph exists for this project yet.</div>
          <button
            className="btn primary"
            style={{ marginTop: 12 }}
            disabled={generate.isPending}
            onClick={() => generate.mutate()}
          >
            {generate.isPending ? "Generating…" : "Generate graph"}
          </button>
        </section>
      )}

      {hasGraph && (
        <>
          <section className="grid grid-3">
            <div className="card metric">
              <div className="label">Nodes</div>
              <div className="value">
                {summary.data?.node_count ?? graph.data?.node_count ?? 0}
              </div>
              <div className="delta">
                {summary.data?.version
                  ? "Version " + summary.data.version
                  : graph.data?.version
                    ? "Version " + graph.data.version
                    : ""}
              </div>
            </div>
            <div className="card metric">
              <div className="label">Relationships</div>
              <div className="value">
                {summary.data?.edge_count ?? graph.data?.edge_count ?? 0}
              </div>
              <div className="delta">Persisted graph edges</div>
            </div>
            <div className="card metric">
              <div className="label">Status</div>
              <div className="value" style={{ fontSize: 22 }}>
                {summary.data?.status ?? graph.data?.status ?? "unknown"}
              </div>
              <div className="delta">
                {summary.data?.graph_version ??
                  graph.data?.graph_version ??
                  ""}
              </div>
            </div>
          </section>

          <section className="grid grid-2">
            <section className="card pad">
              <div className="row">
                <h3>Node types</h3>
                <span className="tag">{nodeTypes.length}</span>
              </div>
              <div className="list" style={{ marginTop: 12 }}>
                {nodeTypes.map(([type, count]) => (
                  <div className="list-item" key={type}>
                    <div className="row">
                      <span>{type}</span>
                      <b>{count}</b>
                    </div>
                  </div>
                ))}
                {nodeTypes.length === 0 && (
                  <div className="empty">
                    <div className="big">∅</div>
                    <div>No node-type counts are available.</div>
                  </div>
                )}
              </div>
            </section>

            <section className="card pad">
              <div className="row">
                <h3>Relationship types</h3>
                <span className="tag">{relationTypes.length}</span>
              </div>
              <div className="list" style={{ marginTop: 12 }}>
                {relationTypes.map(([type, count]) => (
                  <div className="list-item" key={type}>
                    <div className="row">
                      <span>{type}</span>
                      <b>{count}</b>
                    </div>
                  </div>
                ))}
                {relationTypes.length === 0 && (
                  <div className="empty">
                    <div className="big">∅</div>
                    <div>No relationship-type counts are available.</div>
                  </div>
                )}
              </div>
            </section>
          </section>

          <section className="card pad">
            <h3>Graph provenance</h3>
            <div className="stack" style={{ marginTop: 12 }}>
              <div className="row">
                <span className="muted">Context hash</span>
                <code>{summary.data?.context_hash ?? graph.data?.context_hash ?? "n/a"}</code>
              </div>
              <div className="row">
                <span className="muted">Literature run</span>
                <span>{graph.data?.source_literature_run_id ?? "n/a"}</span>
              </div>
              <div className="row">
                <span className="muted">Research plan</span>
                <span>{graph.data?.research_plan_id ?? "n/a"}</span>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
