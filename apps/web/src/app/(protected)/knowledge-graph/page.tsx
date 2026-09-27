"use client";

import { useEffect, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function KnowledgeGraphPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [projectId, setProjectId] = useState("");
  const [startNodeId, setStartNodeId] = useState("");
  const [maxDepth, setMaxDepth] = useState("3");
  const [maxNodes, setMaxNodes] = useState("100");
  const [relationTypes, setRelationTypes] = useState("");

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

  const graph = useQuery({
    queryKey: ["knowledge-graph", projectId],
    queryFn: () => api.knowledgeGraph(projectId),
    enabled: !!projectId,
    retry: false,
  });

  const summary = useQuery({
    queryKey: ["knowledge-graph-summary", projectId],
    queryFn: () => api.knowledgeGraphSummary(projectId),
    enabled: !!projectId,
    retry: false,
  });

  const generate = useMutation({
    mutationFn: () =>
      api.generateKnowledgeGraph(
        projectId,
        false,
        true,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["knowledge-graph", projectId],
      });
      queryClient.invalidateQueries({
        queryKey: [
          "knowledge-graph-summary",
          projectId,
        ],
      });
    },
  });

  const traverse = useMutation({
    mutationFn: () =>
      api.queryKnowledgeGraph(projectId, {
        start_node_id: startNodeId.trim(),
        max_depth: Number(maxDepth) || 3,
        max_nodes: Number(maxNodes) || 100,
        relation_types: relationTypes
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      }),
  });

  const exportGraph = useMutation({
    mutationFn: () => api.graphExport(projectId),
    onSuccess: (data) => {
      const blob = new Blob(
        [JSON.stringify(data, null, 2)],
        { type: "application/json" },
      );

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = url;
      anchor.download =
        `knowledge-graph-${projectId}.json`;

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      URL.revokeObjectURL(url);
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
          Project intelligence
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Knowledge Graph
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Versioned graph builds, bounded traversal,
          relationship summaries, provenance, and JSON
          export are connected directly to the backend.
        </p>
      </header>

      <section className="card p-5">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <div className="muted text-sm">
              Project
            </div>

            <select
              className="input mt-2 min-w-72"
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

          <div className="flex gap-2 self-end">
            <button
              className="btn btn-primary"
              disabled={
                !projectId ||
                generate.isPending
              }
              onClick={() => generate.mutate()}
            >
              {generate.isPending
                ? "Generating…"
                : "Generate graph"}
            </button>

            <button
              className="btn btn-secondary"
              disabled={
                !projectId ||
                exportGraph.isPending
              }
              onClick={() =>
                exportGraph.mutate()
              }
            >
              {exportGraph.isPending
                ? "Exporting…"
                : "Export JSON"}
            </button>
          </div>
        </div>

        {generate.data && (
          <div className="muted text-sm mt-4">
            Build status:{" "}
            {generate.data.status}
            {generate.data.job_id
              ? " · job " +
                generate.data.job_id
              : ""}
          </div>
        )}

        {generate.error && (
          <div
            className="text-sm mt-3"
            style={{ color: "var(--danger)" }}
          >
            {generate.error.message}
          </div>
        )}

        {exportGraph.error && (
          <div
            className="text-sm mt-3"
            style={{ color: "var(--danger)" }}
          >
            {exportGraph.error.message}
          </div>
        )}
      </section>

      <div className="grid md:grid-cols-4 gap-4">
        <Metric
          label="Nodes"
          value={
            summary.data?.node_count ??
            graph.data?.node_count ??
            "—"
          }
        />

        <Metric
          label="Edges"
          value={
            summary.data?.edge_count ??
            graph.data?.edge_count ??
            "—"
          }
        />

        <Metric
          label="Version"
          value={
            summary.data?.version ??
            graph.data?.version ??
            "—"
          }
        />

        <Metric
          label="Status"
          value={
            summary.data?.status ??
            graph.data?.status ??
            "—"
          }
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <section className="card p-5">
          <h2 className="font-semibold">
            Graph metadata
          </h2>

          {graph.isPending && (
            <div className="muted text-sm mt-4">
              Loading graph…
            </div>
          )}

          {graph.error && (
            <div className="muted text-sm mt-4">
              Graph unavailable:{" "}
              {graph.error.message}
            </div>
          )}

          {graph.data && (
            <div className="mt-4 space-y-3 text-sm">
              <Meta
                label="Graph version"
                value={graph.data.graph_version}
              />

              <Meta
                label="Context hash"
                value={graph.data.context_hash}
              />

              <Meta
                label="Literature run"
                value={
                  graph.data
                    .source_literature_run_id ??
                  "None"
                }
              />

              <Meta
                label="Research plan"
                value={
                  graph.data.research_plan_id ??
                  "None"
                }
              />

              <Meta
                label="Created"
                value={
                  new Date(
                    graph.data.created_at,
                  ).toLocaleString()
                }
              />
            </div>
          )}
        </section>

        <section className="card p-5">
          <h2 className="font-semibold">
            Node types
          </h2>

          <div className="mt-4 space-y-2">
            {Object.entries(
              summary.data?.node_type_counts ??
                {},
            ).map(([key, value]) => (
              <div
                key={key}
                className="flex justify-between text-sm"
              >
                <span>{key}</span>
                <span className="muted">
                  {value}
                </span>
              </div>
            ))}

            {!Object.keys(
              summary.data?.node_type_counts ??
                {},
            ).length && (
              <div className="muted text-sm">
                No node type counts available.
              </div>
            )}
          </div>

          <h2 className="font-semibold mt-7">
            Relation types
          </h2>

          <div className="mt-4 space-y-2">
            {Object.entries(
              summary.data?.relation_type_counts ??
                {},
            ).map(([key, value]) => (
              <div
                key={key}
                className="flex justify-between text-sm"
              >
                <span>{key}</span>
                <span className="muted">
                  {value}
                </span>
              </div>
            ))}

            {!Object.keys(
              summary.data?.relation_type_counts ??
                {},
            ).length && (
              <div className="muted text-sm">
                No relation type counts available.
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="card p-5">
        <h2 className="font-semibold">
          Bounded graph traversal
        </h2>

        <p className="muted text-sm mt-1">
          Enter a graph node UUID to traverse the current
          version with backend-enforced bounds.
        </p>

        <div className="grid md:grid-cols-4 gap-3 mt-4">
          <input
            className="input md:col-span-2"
            placeholder="Start node UUID"
            value={startNodeId}
            onChange={(event) =>
              setStartNodeId(event.target.value)
            }
          />

          <input
            className="input"
            type="number"
            min="1"
            max="10"
            placeholder="Max depth"
            value={maxDepth}
            onChange={(event) =>
              setMaxDepth(event.target.value)
            }
          />

          <input
            className="input"
            type="number"
            min="1"
            max="10000"
            placeholder="Max nodes"
            value={maxNodes}
            onChange={(event) =>
              setMaxNodes(event.target.value)
            }
          />
        </div>

        <input
          className="input mt-3"
          placeholder="Relation types, comma separated (optional)"
          value={relationTypes}
          onChange={(event) =>
            setRelationTypes(event.target.value)
          }
        />

        <button
          className="btn btn-primary mt-4"
          disabled={
            !projectId ||
            !startNodeId.trim() ||
            traverse.isPending
          }
          onClick={() => traverse.mutate()}
        >
          {traverse.isPending
            ? "Traversing…"
            : "Run traversal"}
        </button>

        {traverse.error && (
          <div
            className="text-sm mt-3"
            style={{ color: "var(--danger)" }}
          >
            {traverse.error.message}
          </div>
        )}

        {traverse.data && (
          <div className="mt-5 space-y-4">
            <div className="grid md:grid-cols-3 gap-3">
              <Metric
                label="Returned nodes"
                value={traverse.data.nodes.length}
              />

              <Metric
                label="Returned edges"
                value={traverse.data.edges.length}
              />

              <Metric
                label="Max depth"
                value={traverse.data.max_depth}
              />
            </div>

            <pre className="rounded-xl border p-4 overflow-auto text-xs">
              {JSON.stringify(
                {
                  nodes: traverse.data.nodes,
                  edges: traverse.data.edges,
                },
                null,
                2,
              )}
            </pre>
          </div>
        )}
      </section>
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
    <div className="card p-4">
      <div className="muted text-sm">
        {label}
      </div>

      <div className="text-xl font-semibold mt-2">
        {value}
      </div>
    </div>
  );
}

function Meta({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="muted text-xs">
        {label}
      </div>

      <div className="mt-1 break-all">
        {value}
      </div>
    </div>
  );
}