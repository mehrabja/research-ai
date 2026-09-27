"use client";

import { useEffect, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function PlanningPage() {
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

  const plan = useQuery({
    queryKey: ["research-plan", projectId],
    queryFn: () => api.researchPlan(projectId),
    enabled: !!projectId,
    retry: false,
  });

  const coverage = useQuery({
    queryKey: ["research-plan-coverage", projectId],
    queryFn: () => api.researchPlanCoverage(projectId),
    enabled: !!projectId && !!plan.data,
    retry: false,
  });

  const validation = useQuery({
    queryKey: ["research-plan-validation", projectId],
    queryFn: () => api.validateResearchPlan(projectId),
    enabled: !!projectId && !!plan.data,
    retry: false,
  });

  const [objective, setObjective] = useState("");
  const [planningMode, setPlanningMode] = useState("");

  useEffect(() => {
    if (!plan.data) return;

    setObjective(
      plan.data.research_objective_snapshot ?? "",
    );

    setPlanningMode(
      plan.data.planning_mode ?? "",
    );
  }, [plan.data]);

  const generate = useMutation({
    mutationFn: () =>
      api.generateResearchPlan(
        projectId,
        false,
        true,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["research-plan", projectId],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "research-plan-coverage",
          projectId,
        ],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "research-plan-validation",
          projectId,
        ],
      });
    },
  });

  const save = useMutation({
    mutationFn: () =>
      api.saveResearchPlan(
        projectId,
        {
          research_objective_snapshot:
            objective.trim() || null,
          planning_mode:
            planningMode.trim() || null,
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["research-plan", projectId],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "research-plan-coverage",
          projectId,
        ],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "research-plan-validation",
          projectId,
        ],
      });
    },
  });

  const restore = useMutation({
    mutationFn: (version: number) =>
      api.restoreResearchPlan(
        projectId,
        version,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["research-plan", projectId],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "research-plan-coverage",
          projectId,
        ],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "research-plan-validation",
          projectId,
        ],
      });
    },
  });

  const sections = plan.data?.sections ?? [];
  const evidenceRequirements =
    plan.data?.evidence_requirements ?? [];

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
          Research planning
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Planning
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Versioned research plans, evidence
          requirements, coverage, validation, and
          restoration are backed by the project planning
          API.
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

          <button
            className="btn btn-primary self-end"
            disabled={
              !projectId || generate.isPending
            }
            onClick={() => generate.mutate()}
          >
            {generate.isPending
              ? "Generating…"
              : "Generate research plan"}
          </button>
        </div>

        {generate.data && (
          <div className="muted text-sm mt-4">
            Status: {generate.data.status}
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
      </section>

      {plan.isPending && (
        <section className="card p-6 muted">
          Loading current research plan…
        </section>
      )}

      {!plan.isPending && plan.isError && (
        <section className="card p-6">
          <div className="font-medium">
            No current plan
          </div>

          <p className="muted text-sm mt-2">
            Generate the first research plan for this
            project.
          </p>

          <div
            className="text-sm mt-3"
            style={{ color: "var(--danger)" }}
          >
            {plan.error.message}
          </div>
        </section>
      )}

      {plan.data && (
        <>
          <div className="grid md:grid-cols-4 gap-4">
            <Metric
              label="Version"
              value={plan.data.version}
            />

            <Metric
              label="Sections"
              value={sections.length}
            />

            <Metric
              label="Evidence requirements"
              value={evidenceRequirements.length}
            />

            <Metric
              label="Coverage"
              value={
                plan.data.coverage_score != null
                  ? (
                      plan.data.coverage_score * 100
                    ).toFixed(1) + "%"
                  : "—"
              }
            />
          </div>

          <section className="card p-5">
            <h2 className="font-semibold">
              Plan context
            </h2>

            <div className="grid md:grid-cols-2 gap-4 mt-5">
              <label>
                <div className="muted text-sm">
                  Research objective
                </div>

                <textarea
                  className="input mt-2 min-h-32"
                  value={objective}
                  onChange={(event) =>
                    setObjective(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label>
                <div className="muted text-sm">
                  Planning mode
                </div>

                <input
                  className="input mt-2"
                  value={planningMode}
                  onChange={(event) =>
                    setPlanningMode(
                      event.target.value,
                    )
                  }
                />
              </label>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                className="btn btn-primary"
                disabled={save.isPending}
                onClick={() => save.mutate()}
              >
                {save.isPending
                  ? "Saving…"
                  : "Save revision"}
              </button>

              {save.isSuccess && (
                <span className="muted text-sm self-center">
                  Saved
                </span>
              )}

              {save.error && (
                <span
                  className="text-sm self-center"
                  style={{
                    color: "var(--danger)",
                  }}
                >
                  {save.error.message}
                </span>
              )}
            </div>
          </section>

          <section className="card overflow-hidden">
            <div className="px-5 py-4 border-b">
              <div className="font-semibold">
                Plan sections
              </div>
            </div>

            <div className="divide-y">
              {sections.map((section) => (
                <div
                  key={section.id}
                  className="px-5 py-4"
                >
                  <div className="flex justify-between gap-4">
                    <div>
                      <div className="font-medium">
                        {section.title}
                      </div>

                      <div className="muted text-sm mt-1">
                        {section.section_key} ·{" "}
                        {section.section_type}
                      </div>
                    </div>

                    <div className="text-right">
                      <div>
                        {section.word_budget} words
                      </div>

                      <div className="muted text-xs mt-1">
                        target{" "}
                        {(
                          section.evidence_coverage_target *
                          100
                        ).toFixed(0)}
                        %
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {!sections.length && (
                <div className="p-6 muted text-sm">
                  No plan sections available.
                </div>
              )}
            </div>
          </section>

          <div className="grid lg:grid-cols-2 gap-5">
            <section className="card p-5">
              <h2 className="font-semibold">
                Coverage
              </h2>

              <div className="mt-4 text-3xl font-semibold">
                {coverage.data
                  ? (
                      coverage.data.coverage_score *
                      100
                    ).toFixed(1) + "%"
                  : "—"}
              </div>

              <div className="muted text-sm mt-1">
                {coverage.data?.coverage_state ??
                  "Unavailable"}
              </div>

              {coverage.data?.per_requirement?.length ? (
                <div className="mt-4 space-y-2">
                  {coverage.data.per_requirement
                    .slice(0, 8)
                    .map((item, index) => (
                      <div
                        key={index}
                        className="rounded-lg border p-3 text-xs"
                        style={{
                          borderColor:
                            "var(--line)",
                        }}
                      >
                        {JSON.stringify(item)}
                      </div>
                    ))}
                </div>
              ) : (
                <div className="muted text-xs mt-4">
                  No per-requirement coverage details.
                </div>
              )}
            </section>

            <section className="card p-5">
              <h2 className="font-semibold">
                Validation
              </h2>

              <div className="mt-4">
                <div className="text-xl font-semibold">
                  {validation.data
                    ?.validation_status ??
                    "—"}
                </div>

                {validation.data
                  ?.completeness_score != null && (
                  <div className="muted text-sm mt-1">
                    completeness{" "}
                    {(
                      validation.data
                        .completeness_score *
                      100
                    ).toFixed(1)}
                    %
                  </div>
                )}
              </div>

              {!!validation.data
                ?.validation_errors.length && (
                <div className="mt-4 space-y-2">
                  {validation.data.validation_errors.map(
                    (error) => (
                      <div
                        key={error}
                        className="text-sm"
                        style={{
                          color:
                            "var(--danger)",
                        }}
                      >
                        {error}
                      </div>
                    ),
                  )}
                </div>
              )}
            </section>
          </div>

          <section className="card overflow-hidden">
            <div className="px-5 py-4 border-b">
              <div className="font-semibold">
                Evidence requirements
              </div>
            </div>

            <div className="divide-y">
              {evidenceRequirements.map(
                (requirement) => (
                  <div
                    key={requirement.id}
                    className="px-5 py-4"
                  >
                    <div className="font-medium">
                      {requirement.requirement_key}
                    </div>

                    <div className="muted text-sm mt-1">
                      {requirement.description}
                    </div>

                    <div className="muted text-xs mt-2">
                      {requirement.required
                        ? "Required"
                        : "Optional"}{" "}
                      · priority{" "}
                      {requirement.priority}
                      {requirement.min_sources !=
                      null
                        ? " · min " +
                          requirement.min_sources +
                          " sources"
                        : ""}
                      {requirement.max_sources !=
                      null
                        ? " · max " +
                          requirement.max_sources +
                          " sources"
                        : ""}
                    </div>
                  </div>
                ),
              )}

              {!evidenceRequirements.length && (
                <div className="p-6 muted text-sm">
                  No evidence requirements available.
                </div>
              )}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="font-semibold">
              Current version
            </h2>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <span className="muted text-sm">
                Version {plan.data.version} ·{" "}
                {plan.data.status}
              </span>

              <button
                className="btn btn-secondary text-sm"
                disabled={
                  restore.isPending ||
                  plan.data.version <= 1
                }
                onClick={() =>
                  restore.mutate(
                    plan.data.version - 1,
                  )
                }
              >
                {restore.isPending
                  ? "Restoring…"
                  : "Restore previous version"}
              </button>
            </div>

            {restore.error && (
              <div
                className="text-sm mt-3"
                style={{
                  color: "var(--danger)",
                }}
              >
                {restore.error.message}
              </div>
            )}
          </section>
        </>
      )}
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