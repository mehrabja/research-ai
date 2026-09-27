"use client";

import { useEffect, useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function ResearchPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [projectId, setProjectId] = useState("");

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

  const project = useQuery({
    queryKey: ["project", projectId, workspaceId],
    queryFn: () =>
      api.project(projectId, workspaceId!),
    enabled: !!workspaceId && !!projectId,
  });

  const [form, setForm] = useState({
    name: "",
    domain: "",
    description: "",
    research_objective: "",
    research_questions: "",
    hypotheses: "",
    scope: "",
    constraints: "",
    status: "draft",
  });

  useEffect(() => {
    const data = project.data;
    if (!data) return;

    setForm({
      name: data.name,
      domain: data.domain ?? "",
      description: data.description ?? "",
      research_objective:
        data.research_objective ?? "",
      research_questions:
        data.research_questions.join("\n"),
      hypotheses:
        data.hypotheses.join("\n"),
      scope: data.scope ?? "",
      constraints: data.constraints ?? "",
      status: data.status,
    });
  }, [project.data]);

  const update = useMutation({
    mutationFn: () =>
      api.updateProject(
        projectId,
        workspaceId!,
        {
          name: form.name.trim(),
          domain: form.domain.trim() || null,
          description:
            form.description.trim() || null,
          research_objective:
            form.research_objective.trim() || null,
          research_questions:
            form.research_questions
              .split("\n")
              .map((x) => x.trim())
              .filter(Boolean),
          hypotheses:
            form.hypotheses
              .split("\n")
              .map((x) => x.trim())
              .filter(Boolean),
          scope: form.scope.trim() || null,
          constraints:
            form.constraints.trim() || null,
          status:
            form.status as
              | "draft"
              | "active"
              | "archived",
        },
      ),

    onSuccess: (data) => {
      queryClient.setQueryData(
        ["project", projectId, workspaceId],
        data,
      );

      queryClient.invalidateQueries({
        queryKey: ["projects", workspaceId],
      });
    },
  });

  const selectedProject = useMemo(
    () =>
      projects.data?.items.find(
        (item) => item.id === projectId,
      ),
    [projects.data, projectId],
  );

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
          Research workspace
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Research
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Research objectives, questions, hypotheses,
          scope, and constraints are stored on the
          selected project and remain authoritative
          on the backend.
        </p>
      </header>

      <section className="card p-5">
        <label className="muted text-sm">
          Project
        </label>

        <select
          className="input mt-2"
          value={projectId}
          onChange={(event) =>
            setProjectId(event.target.value)
          }
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

        {selectedProject && (
          <div className="muted text-xs mt-2">
            {selectedProject.report_count} reports ·{" "}
            {selectedProject.status}
          </div>
        )}
      </section>

      {project.isPending && (
        <div className="card p-6 muted">
          Loading research context…
        </div>
      )}

      {project.error && (
        <div
          className="card p-6"
          style={{ color: "var(--danger)" }}
        >
          {project.error.message}
        </div>
      )}

      {project.data && (
        <>
          <section className="card p-5">
            <h2 className="font-semibold">
              Research definition
            </h2>

            <div className="grid md:grid-cols-2 gap-4 mt-5">
              <Field
                label="Project name"
                value={form.name}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    name: value,
                  }))
                }
              />

              <Field
                label="Domain"
                value={form.domain}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    domain: value,
                  }))
                }
              />

              <TextArea
                label="Description"
                value={form.description}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    description: value,
                  }))
                }
              />

              <TextArea
                label="Research objective"
                value={form.research_objective}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    research_objective: value,
                  }))
                }
              />

              <TextArea
                label="Research questions"
                help="One question per line"
                value={form.research_questions}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    research_questions: value,
                  }))
                }
              />

              <TextArea
                label="Hypotheses"
                help="One hypothesis per line"
                value={form.hypotheses}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    hypotheses: value,
                  }))
                }
              />

              <TextArea
                label="Scope"
                value={form.scope}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    scope: value,
                  }))
                }
              />

              <TextArea
                label="Constraints"
                value={form.constraints}
                onChange={(value) =>
                  setForm((x) => ({
                    ...x,
                    constraints: value,
                  }))
                }
              />
            </div>

            <div className="mt-5 max-w-xs">
              <label className="muted text-sm">
                Status
              </label>

              <select
                className="input mt-2"
                value={form.status}
                onChange={(event) =>
                  setForm((x) => ({
                    ...x,
                    status: event.target.value,
                  }))
                }
              >
                <option value="draft">
                  draft
                </option>
                <option value="active">
                  active
                </option>
                <option value="archived">
                  archived
                </option>
              </select>
            </div>

            <div className="mt-5 flex items-center gap-3">
              <button
                className="btn btn-primary"
                disabled={
                  update.isPending ||
                  !form.name.trim()
                }
                onClick={() => update.mutate()}
              >
                {update.isPending
                  ? "Saving…"
                  : "Save research"}
              </button>

              {update.isSuccess && (
                <span className="text-sm muted">
                  Saved
                </span>
              )}

              {update.error && (
                <span
                  className="text-sm"
                  style={{
                    color: "var(--danger)",
                  }}
                >
                  {update.error.message}
                </span>
              )}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="font-semibold">
              Current research state
            </h2>

            <div className="grid md:grid-cols-3 gap-4 mt-5">
              <Metric
                label="Questions"
                value={
                  project.data.research_questions
                    .length
                }
              />

              <Metric
                label="Hypotheses"
                value={
                  project.data.hypotheses.length
                }
              />

              <Metric
                label="Reports"
                value={project.data.report_count}
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <div className="muted text-sm">
        {label}
      </div>

      <input
        className="input mt-2"
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
      />
    </label>
  );
}

function TextArea({
  label,
  help,
  value,
  onChange,
}: {
  label: string;
  help?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="md:col-span-1">
      <div className="muted text-sm">
        {label}
      </div>

      {help && (
        <div className="muted text-xs mt-1">
          {help}
        </div>
      )}

      <textarea
        className="input mt-2 min-h-32"
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
      />
    </label>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-xl border p-4">
      <div className="muted text-sm">
        {label}
      </div>

      <div className="text-2xl font-semibold mt-2">
        {value}
      </div>
    </div>
  );
}