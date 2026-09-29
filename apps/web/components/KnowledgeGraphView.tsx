"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";
import { useResearchContext } from "@/lib/research-context";
import {
  generateKnowledgeGraph,
  getKnowledgeGraph,
  getKnowledgeGraphNeighbors,
  getKnowledgeGraphSummary,
  knowledgeGraphExportUrl,
  listKnowledgeGraphNodes,
} from "@/lib/api/knowledgeGraph";

function neighborLabel(value: {
  [key: string]: unknown;
}): string {
  if (typeof value.label === "string" && value.label.trim()) {
    return value.label;
  }
  if (typeof value.node_key === "string" && value.node_key.trim()) {
    return value.node_key;
  }
  return "Neighbor";
}

function KnowledgeGraphView() {
  const queryClient = useQueryClient();
  const {
    projectId: activeProjectId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
  } = useResearchContext();
  const [nodeQuery, setNodeQuery] = useState("");
  const [nodeType, setNodeType] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

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

  const hasGraph = Boolean(graph.data || summary.data);

  const nodes = useQuery({
    queryKey: ["knowledge-graph-nodes", activeProjectId, nodeQuery, nodeType],
    queryFn: () =>
      listKnowledgeGraphNodes(activeProjectId!, {
        q: nodeQuery.trim() || undefined,
        nodeType: nodeType || undefined,
        limit: 100,
      }),
    enabled: Boolean(activeProjectId && hasGraph),
    staleTime: 10_000,
  });

  const effectiveSelectedNodeId =
    selectedNodeId && nodes.data?.some((node) => node.id === selectedNodeId)
      ? selectedNodeId
      : nodes.data?.[0]?.id ?? null;

  const neighbors = useQuery({
    queryKey: ["knowledge-graph-neighbors", activeProjectId, effectiveSelectedNodeId],
    queryFn: () =>
      getKnowledgeGraphNeighbors(activeProjectId!, effectiveSelectedNodeId!, {
        direction: "both",
        limit: 50,
      }),
    enabled: Boolean(activeProjectId && effectiveSelectedNodeId && hasGraph),
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
      await queryClient.invalidateQueries({
        queryKey: ["knowledge-graph-nodes", activeProjectId],
      });
    },
  });

  const errors = [
    workspaces.error,
    projects.error,
    graph.error,
    summary.error,
    nodes.error,
    neighbors.error,
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
            void nodes.refetch();
            void neighbors.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  const nodeTypes = Object.entries(
    summary.data?.node_type_counts ?? {},
  );
  const relationTypes = Object.entries(
    summary.data?.relation_type_counts ?? {},
  );
  const selectedNode = nodes.data?.find(
    (node) => node.id === effectiveSelectedNodeId,
  );

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Project knowledge</div>
            <h2 style={{ marginTop: 4 }}>Knowledge graph</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Persisted graph topology, provenance, and bounded neighborhood
              traversal. No synthetic nodes are rendered.
            </p>
          </div>
          <div className="actions">
            <button
              className="btn primary"
              disabled={!activeProjectId || generate.isPending}
              onClick={() => generate.mutate()}
            >
              {generate.isPending
                ? "Generating…"
                : hasGraph
                  ? "Regenerate"
                  : "Generate graph"}
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
          <div>
            Create a project in Workspace before generating a knowledge graph.
          </div>
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
                <div>
                  <h3>Nodes</h3>
                  <div className="muted small">
                    Select a persisted node to inspect its neighbors.
                  </div>
                </div>
                <span className="tag">
                  {nodes.data?.length ?? 0}
                </span>
              </div>

              <div className="row" style={{ marginTop: 12 }}>
                <input
                  className="input"
                  style={{ flex: 1 }}
                  value={nodeQuery}
                  onChange={(event) => setNodeQuery(event.target.value)}
                  placeholder="Filter by node label or key…"
                  aria-label="Knowledge graph node filter"
                />
                <select
                  className="input"
                  style={{ width: 220 }}
                  value={nodeType}
                  onChange={(event) => {
                    setNodeType(event.target.value);
                    setSelectedNodeId(null);
                  }}
                  aria-label="Knowledge graph node type"
                >
                  <option value="">All node types</option>
                  {nodeTypes.map(([type]) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </div>

              <div className="list" style={{ marginTop: 10 }}>
                {(nodes.data ?? []).map((node) => (
                  <button
                    key={node.id}
                    type="button"
                    className="list-item"
                    onClick={() => setSelectedNodeId(node.id)}
                    style={{
                      textAlign: "left",
                      border:
                        node.id === selectedNodeId
                          ? "1px solid var(--primary)"
                          : undefined,
                    }}
                  >
                    <div className="row">
                      <strong>{node.label ?? node.node_key}</strong>
                      <span className="tag">{node.node_type}</span>
                    </div>
                    <div className="meta" style={{ marginTop: 4 }}>
                      {node.node_key}
                    </div>
                  </button>
                ))}
                {nodes.data?.length === 0 && (
                  <div className="empty">
                    <div className="big">∅</div>
                    <div>No graph nodes match the current filter.</div>
                  </div>
                )}
              </div>
            </section>

            <section className="card pad">
              <div className="row">
                <div>
                  <h3>Selected node</h3>
                  <div className="muted small">
                    Bounded two-way neighbor traversal from the persisted graph.
                  </div>
                </div>
              </div>

              {!selectedNode && (
                <div className="empty" style={{ marginTop: 12 }}>
                  <div className="big">∅</div>
                  <div>Select a node to inspect its relationships.</div>
                </div>
              )}

              {selectedNode && (
                <>
                  <div
                    className="card"
                    style={{ marginTop: 12, padding: 12 }}
                  >
                    <div className="strong">
                      {selectedNode.label ?? selectedNode.node_key}
                    </div>
                    <div className="meta" style={{ marginTop: 4 }}>
                      {selectedNode.node_type} · {selectedNode.node_key}
                    </div>
                  </div>

                  <div className="list" style={{ marginTop: 10 }}>
                    {(neighbors.data ?? []).map((item) => (
                      <div className="list-item" key={item.edge_id}>
                        <div className="row">
                          <strong>{neighborLabel(item.neighbor)}</strong>
                          <span className="tag">{item.relation_type}</span>
                        </div>
                        <div className="meta" style={{ marginTop: 4 }}>
                          {item.direction} ·{" "}
                          {item.provenance_type}
                          {item.provenance_ref
                            ? " · " + item.provenance_ref
                            : ""}
                        </div>
                        {item.confidence !== null && (
                          <div className="muted tiny" style={{ marginTop: 4 }}>
                            Confidence {item.confidence.toFixed(2)} · Weight{" "}
                            {item.weight.toFixed(2)}
                          </div>
                        )}
                      </div>
                    ))}
                    {neighbors.data?.length === 0 && (
                      <div className="empty">
                        <div>No neighbors were returned for this node.</div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </section>
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
                <code>
                  {summary.data?.context_hash ??
                    graph.data?.context_hash ??
                    "n/a"}
                </code>
              </div>
              <div className="row">
                <span className="muted">Literature run</span>
                <span>
                  {graph.data?.source_literature_run_id ?? "n/a"}
                </span>
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
export default KnowledgeGraphView;
