"use client";

import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  archiveProject,
  createProject,
  type Project,
} from "@/lib/api/projects";
import {
  reactivateWorkspace,
  suspendWorkspace,
} from "@/lib/api/workspaces";
import { useResearchContext } from "@/lib/research-context";

export default function WorkspaceProjects() {
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");
  const queryClient = useQueryClient();

  const {
    workspaceId: activeWorkspaceId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
    contextHref,
  } = useResearchContext();

  const create = useMutation({
    mutationFn: () =>
      createProject({
        workspaceId: activeWorkspaceId ?? undefined,
        name: projectName.trim(),
        description: description.trim(),
      }),
    onSuccess: async () => {
      setProjectName("");
      setDescription("");
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const archive = useMutation({
    mutationFn: (project: Project) =>
      archiveProject(project.id, activeWorkspaceId ?? undefined),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const lifecycle = useMutation({
    mutationFn: async (action: "suspend" | "reactivate") => {
      if (!activeWorkspaceId) throw new Error("No workspace is selected.");
      return action === "suspend"
        ? suspendWorkspace(activeWorkspaceId)
        : reactivateWorkspace(activeWorkspaceId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
    },
  });

  const busy =
    workspaces.isPending ||
    projects.isPending ||
    create.isPending ||
    archive.isPending ||
    lifecycle.isPending;

  if (workspaces.error) {
    return (
      <section className="card pad" role="alert">
        <h2>Workspace unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {workspaces.error.message}
        </p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 14 }}
          onClick={() => void workspaces.refetch()}
        >
          Retry
        </button>
      </section>
    );
  }

  const activeWorkspace =
    (workspaces.data ?? []).find(
      (workspace) => workspace.id === activeWorkspaceId,
    ) ?? null;
  const isSuspended = activeWorkspace?.status === "suspended";
  const owner = activeWorkspace?.role === "owner";

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <h2>Workspace lifecycle</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Owner-only suspend/reactivate controls backed by the workspace lifecycle API.
            </p>
          </div>
          <span className={"tag " + (isSuspended ? "" : "success")}>
            {activeWorkspace?.status ?? "Loading…"}
          </span>
        </div>
        {lifecycle.error && (
          <p className="muted" role="alert" style={{ marginTop: 10 }}>
            {lifecycle.error instanceof Error
              ? lifecycle.error.message
              : "Workspace lifecycle request failed."}
          </p>
        )}
        <div className="actions" style={{ marginTop: 12 }}>
          {owner && isSuspended ? (
            <button
              className="btn primary"
              type="button"
              disabled={busy}
              onClick={() => lifecycle.mutate("reactivate")}
            >
              {lifecycle.isPending ? "Reactivating…" : "Reactivate workspace"}
            </button>
          ) : owner ? (
            <button
              className="btn"
              type="button"
              disabled={busy}
              onClick={() => lifecycle.mutate("suspend")}
            >
              {lifecycle.isPending ? "Suspending…" : "Suspend workspace"}
            </button>
          ) : (
            <span className="muted small">Only the workspace owner can change lifecycle state.</span>
          )}
        </div>
      </section>
      <section className="grid grid-2">
        <div className="card pad">
          <div className="row">
            <div>
              <h2>Projects</h2>
              <p className="muted small" style={{ marginTop: 4 }}>
                Projects returned by the backend for this workspace.
              </p>
            </div>
            <span className="tag">{projects.data?.length ?? 0}</span>
          </div>

          {projects.error && (
            <p className="muted small" role="status" style={{ marginTop: 12 }}>
              Project data is temporarily unavailable for this workspace state.
              Reactivation can still be managed above.
            </p>
          )}

          <div className="list" style={{ marginTop: 12 }}>
            {(projects.data ?? []).map((project) => (
              <article className="list-item" key={project.id}>
                <div className="row">
                  <div style={{ minWidth: 0 }}>
                    <div className="title">{project.name}</div>
                    <div className="meta">
                      {project.domain ?? "No domain"} · {project.status} ·{" "}
                      {project.report_count} reports
                    </div>
                  </div>

                  <div className="actions">
                    <Link
                      className="btn"
                      href={contextHref("/research?projectId="+project.id)}
                    >
                      Research
                    </Link>
                    <button
                      className="btn ghost"
                      type="button"
                      onClick={() => archive.mutate(project)}
                      disabled={busy}
                    >
                      Archive
                    </button>
                  </div>
                </div>
              </article>
            ))}

            {!projects.isPending && (projects.data?.length ?? 0) === 0 && (
              <div className="empty">
                <div className="big">∅</div>
                <div>No projects yet. Create the first research project.</div>
              </div>
            )}
          </div>
        </div>

        <div className="card pad">
          <h2>New project</h2>
          <p className="muted small" style={{ marginTop: 4 }}>
            Creates a real Project record in the selected workspace.
          </p>

          <div className="stack" style={{ marginTop: 14 }}>
            <div className="field">
              <label htmlFor="project-name">Project name</label>
              <input
                id="project-name"
                className="input"
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="e.g. Sparse fMRI decoding study"
                disabled={busy}
              />
            </div>

            <div className="field">
              <label htmlFor="project-description">Description</label>
              <textarea
                id="project-description"
                className="input textarea"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Briefly describe the study."
                disabled={busy}
              />
            </div>

            {(create.error || archive.error) && (
              <p className="muted" role="alert">
                {create.error?.message ?? archive.error?.message}
              </p>
            )}

            <button
              className="btn primary"
              type="button"
              disabled={
                busy ||
                !activeWorkspaceId ||
                projectName.trim().length < 1
              }
              onClick={() => create.mutate()}
            >
              {create.isPending ? "Creating…" : "Create project"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
