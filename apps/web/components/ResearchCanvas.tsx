"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import {
  getResearchCanvas,
  saveResearchCanvas,
  type CanvasEdge,
  type CanvasNode,
  type CanvasViewport,
} from "@/lib/api/research-canvas";
import { ApiError } from "@/lib/api/errors";

function makeNodeId(): string {
  return "node-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
}

function makeEdgeId(): string {
  return "edge-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
}

export default function ResearchCanvas() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [nodes, setNodes] = useState<CanvasNode[]>([]);
  const [edges, setEdges] = useState<CanvasEdge[]>([]);
  const [viewport, setViewport] = useState<CanvasViewport>({
    x: 0,
    y: 0,
    zoom: 1,
  });
  const [revision, setRevision] = useState(1);
  const [sourceNodeId, setSourceNodeId] = useState("");
  const [targetNodeId, setTargetNodeId] = useState("");
  const [feedback, setFeedback] = useState("");
  const queryClient = useQueryClient();

  const workspaces = useQuery({
    queryKey: ["workspaces"],
    queryFn: listWorkspaces,
    staleTime: 30_000,
  });

  const activeWorkspaceId = workspaceId ?? workspaces.data?.[0]?.id;

  const projects = useQuery({
    queryKey: ["projects", activeWorkspaceId],
    queryFn: () => {
      if (!activeWorkspaceId) throw new Error("No workspace is selected.");
      return listProjects(activeWorkspaceId);
    },
    enabled: Boolean(activeWorkspaceId),
    staleTime: 15_000,
  });

  const activeProjectId = projectId ?? projects.data?.[0]?.id;

  const canvas = useQuery({
    queryKey: ["research-canvas", activeProjectId],
    queryFn: () => getResearchCanvas(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 5_000,
  });

  useEffect(() => {
    if (!canvas.data) return;
    const timer = window.setTimeout(() => {
      setNodes(canvas.data?.nodes ?? []);
      setEdges(canvas.data?.edges ?? []);
      setViewport(canvas.data?.viewport ?? { x: 0, y: 0, zoom: 1 });
      setRevision(canvas.data?.revision ?? 1);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [canvas.data]);

  const nodeOptions = useMemo(
    () => nodes.map((node) => ({ id: node.id, title: node.title })),
    [nodes],
  );

  const save = useMutation({
    mutationFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return saveResearchCanvas(activeProjectId, {
        nodes,
        edges,
        viewport,
        expected_revision: revision,
      });
    },
    onSuccess: (data) => {
      setRevision(data.revision);
      queryClient.setQueryData(
        ["research-canvas", activeProjectId],
        data,
      );
      setFeedback("Canvas saved.");
    },
    onError: async (error) => {
      if (
        error instanceof ApiError &&
        error.code === "CANVAS_REVISION_CONFLICT"
      ) {
        setFeedback("Canvas changed elsewhere. Reloading the latest revision.");
        await canvas.refetch();
        return;
      }
      setFeedback(
        error instanceof Error
          ? error.message
          : "Canvas save failed.",
      );
    },
  });

  const addNode = () => {
    setNodes((current) => [
      ...current,
      {
        id: makeNodeId(),
        type: "note",
        title: "New research node",
        body: "",
        x: current.length * 40,
        y: current.length * 40,
      },
    ]);
  };

  const updateNode = (
    nodeId: string,
    changes: Partial<CanvasNode>,
  ) => {
    setNodes((current) =>
      current.map((node) =>
        node.id === nodeId ? { ...node, ...changes } : node,
      ),
    );
  };

  const removeNode = (nodeId: string) => {
    setNodes((current) => current.filter((node) => node.id !== nodeId));
    setEdges((current) =>
      current.filter(
        (edge) => edge.source !== nodeId && edge.target !== nodeId,
      ),
    );
  };

  const connectNodes = () => {
    if (!sourceNodeId || !targetNodeId || sourceNodeId === targetNodeId) {
      return;
    }
    setEdges((current) => {
      if (
        current.some(
          (edge) =>
            edge.source === sourceNodeId &&
            edge.target === targetNodeId,
        )
      ) {
        return current;
      }
      return [
        ...current,
        {
          id: makeEdgeId(),
          source: sourceNodeId,
          target: targetNodeId,
        },
      ];
    });
    setFeedback("Connection added. Save the canvas to persist it.");
  };

  const error = [
    workspaces.error,
    projects.error,
    canvas.error,
  ].find((value): value is Error => value instanceof Error);

  if (error) {
    return (
      <section className="card pad" role="alert">
        <h2>Research canvas unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {error.message}
        </p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 12 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void canvas.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Legacy Phase 13</div>
            <h2 style={{ marginTop: 4 }}>Research Canvas</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Persisted nodes, connections, viewport and revision state.
            </p>
          </div>
          <Link className="btn" href="/evidence">
            Evidence
          </Link>
        </div>

        <div className="grid grid-2" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="canvas-workspace">Workspace</label>
            <select
              id="canvas-workspace"
              className="input"
              value={activeWorkspaceId ?? ""}
              onChange={(event) => {
                setWorkspaceId(event.target.value);
                setProjectId(undefined);
              }}
            >
              {(workspaces.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="canvas-project">Project</label>
            <select
              id="canvas-project"
              className="input"
              value={activeProjectId ?? ""}
              onChange={(event) => setProjectId(event.target.value)}
              disabled={projects.isPending}
            >
              {(projects.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="row" style={{ marginTop: 14 }}>
          <span className="tag">Revision {revision}</span>
          <span className="muted small">
            {nodes.length} nodes · {edges.length} connections
          </span>
        </div>
      </section>

      <section className="card pad">
        <div className="row">
          <h3>Canvas nodes</h3>
          <button className="btn primary" type="button" onClick={addNode}>
            Add node
          </button>
        </div>

        <div className="grid grid-2" style={{ marginTop: 14 }}>
          {nodes.map((node) => (
            <article className="card pad" key={node.id}>
              <div className="field">
                <label htmlFor={"node-title-" + node.id}>Title</label>
                <input
                  id={"node-title-" + node.id}
                  className="input"
                  value={node.title}
                  onChange={(event) =>
                    updateNode(node.id, { title: event.target.value })
                  }
                />
              </div>
              <div className="field" style={{ marginTop: 10 }}>
                <label htmlFor={"node-type-" + node.id}>Type</label>
                <select
                  id={"node-type-" + node.id}
                  className="input"
                  value={node.type}
                  onChange={(event) =>
                    updateNode(node.id, {
                      type: event.target.value as CanvasNode["type"],
                    })
                  }
                >
                  <option value="idea">Idea</option>
                  <option value="evidence">Evidence</option>
                  <option value="draft">Draft</option>
                  <option value="note">Note</option>
                </select>
              </div>
              <div className="field" style={{ marginTop: 10 }}>
                <label htmlFor={"node-body-" + node.id}>Body</label>
                <textarea
                  id={"node-body-" + node.id}
                  className="input textarea"
                  value={node.body}
                  onChange={(event) =>
                    updateNode(node.id, { body: event.target.value })
                  }
                />
              </div>
              <button
                className="btn ghost"
                type="button"
                style={{ marginTop: 10 }}
                onClick={() => removeNode(node.id)}
              >
                Remove node
              </button>
            </article>
          ))}
        </div>

        {nodes.length === 0 && (
          <div className="empty" style={{ marginTop: 14 }}>
            <div className="big">∅</div>
            <div>Start by adding an idea, evidence, draft, or note node.</div>
          </div>
        )}
      </section>

      <section className="card pad">
        <h3>Connections & viewport</h3>
        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="canvas-source">From</label>
            <select
              id="canvas-source"
              className="input"
              value={sourceNodeId}
              onChange={(event) => setSourceNodeId(event.target.value)}
            >
              <option value="">Select node</option>
              {nodeOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="canvas-target">To</label>
            <select
              id="canvas-target"
              className="input"
              value={targetNodeId}
              onChange={(event) => setTargetNodeId(event.target.value)}
            >
              <option value="">Select node</option>
              {nodeOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "end" }}>
            <button
              className="btn"
              type="button"
              onClick={connectNodes}
              disabled={
                !sourceNodeId ||
                !targetNodeId ||
                sourceNodeId === targetNodeId
              }
            >
              Connect
            </button>
          </div>
        </div>

        <div className="grid grid-3" style={{ marginTop: 12 }}>
          <div className="field">
            <label htmlFor="canvas-viewport-x">Viewport X</label>
            <input
              id="canvas-viewport-x"
              className="input"
              type="number"
              value={viewport.x}
              onChange={(event) =>
                setViewport((current) => ({
                  ...current,
                  x: Number(event.target.value) || 0,
                }))
              }
            />
          </div>
          <div className="field">
            <label htmlFor="canvas-viewport-y">Viewport Y</label>
            <input
              id="canvas-viewport-y"
              className="input"
              type="number"
              value={viewport.y}
              onChange={(event) =>
                setViewport((current) => ({
                  ...current,
                  y: Number(event.target.value) || 0,
                }))
              }
            />
          </div>
          <div className="field">
            <label htmlFor="canvas-viewport-zoom">Viewport zoom</label>
            <input
              id="canvas-viewport-zoom"
              className="input"
              type="number"
              min={0.25}
              max={4}
              step={0.25}
              value={viewport.zoom}
              onChange={(event) =>
                setViewport((current) => ({
                  ...current,
                  zoom: Math.min(
                    4,
                    Math.max(0.25, Number(event.target.value) || 1),
                  ),
                }))
              }
            />
          </div>
        </div>

        <button
          className="btn primary"
          type="button"
          style={{ marginTop: 14 }}
          disabled={!activeProjectId || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Saving…" : "Save canvas"}
        </button>

        {feedback && (
          <p className="muted small" role="status" style={{ marginTop: 10 }}>
            {feedback}
          </p>
        )}
      </section>
    </div>
  );
}
