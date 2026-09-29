"use client";

import { useResearchContext } from "@/lib/research-context";

export function ResearchContextSwitcher() {
  const {
    workspaceId,
    projectId,
    reportId,
    workspacesQuery,
    projectsQuery,
    reportsQuery,
    setWorkspace,
    setProject,
    setReport,
    invalid,
    resetContext,
  } = useResearchContext();

  if (invalid) {
    return (
      <div
        className="context-switcher"
        role="alert"
        aria-live="polite"
      >
        <span className="tag danger">
          Context unavailable
        </span>
        <button
          className="btn ghost"
          type="button"
          onClick={resetContext}
        >
          Reset
        </button>
      </div>
    );
  }

  const workspaces = workspacesQuery.data ?? [];
  const projects = projectsQuery.data ?? [];
  const reports = reportsQuery.data ?? [];

  return (
    <div
      className="context-switcher"
      aria-label="Research context"
    >
      <label
        className="sr-only"
        htmlFor="global-workspace"
      >
        Workspace
      </label>
      <select
        id="global-workspace"
        className="context-select"
        value={workspaceId ?? ""}
        onChange={(event) =>
          setWorkspace(event.target.value)
        }
        disabled={
          workspacesQuery.isPending ||
          workspaces.length === 0
        }
        title="Workspace"
      >
        {workspaces.length === 0 ? (
          <option value="">
            No workspace
          </option>
        ) : (
          workspaces.map((workspace) => (
            <option
              key={workspace.id}
              value={workspace.id}
            >
              {workspace.name}
            </option>
          ))
        )}
      </select>

      <label
        className="sr-only"
        htmlFor="global-project"
      >
        Project
      </label>
      <select
        id="global-project"
        className="context-select context-project"
        value={projectId ?? ""}
        onChange={(event) =>
          setProject(event.target.value || null)
        }
        disabled={
          projectsQuery.isPending ||
          projects.length === 0
        }
        title="Project"
      >
        {projects.length === 0 ? (
          <option value="">
            No project
          </option>
        ) : (
          <>
            <option value="">
              Select project
            </option>
            {projects.map((project) => (
              <option
                key={project.id}
                value={project.id}
              >
                {project.name}
              </option>
            ))}
          </>
        )}
      </select>

      <label
        className="sr-only"
        htmlFor="global-report"
      >
        Research report
      </label>
      <select
        id="global-report"
        className="context-select context-report"
        value={reportId ?? ""}
        onChange={(event) =>
          setReport(event.target.value || null)
        }
        disabled={
          !projectId ||
          reportsQuery.isPending ||
          reports.length === 0
        }
        title="Research report"
      >
        {!projectId || reports.length === 0 ? (
          <option value="">
            {!projectId
              ? "Select a project first"
              : "No report"}
          </option>
        ) : (
          <>
            <option value="">
              Select report
            </option>
            {reports.map((report) => (
              <option
                key={report.id}
                value={report.id}
              >
                {report.topic.slice(0, 48)}
              </option>
            ))}
          </>
        )}
      </select>
    </div>
  );
}
