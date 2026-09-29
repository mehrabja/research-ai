"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useResearchContext } from "@/lib/research-context";
import {
  generateResearchPlan,
  getResearchPlanCoverage,
  listResearchPlanVersions,
  saveResearchPlanRevision,
  validateResearchPlan,
  type ResearchPlan,
} from "@/lib/api/researchPlan";

export default function ResearchPlanView() {
  const [objective, setObjective] = useState("");
  const queryClient = useQueryClient();

  const {
    workspaceId: activeWorkspaceId,
    projectId: activeProjectId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
    setWorkspace: setWorkspaceId,
    setProject: setProjectId,
  } = useResearchContext();

  const versions = useQuery({
    queryKey: ["research-plan-versions", activeProjectId],
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return listResearchPlanVersions(activeProjectId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const plan: ResearchPlan | undefined = versions.data?.[0];
  const planObjective =
    objective !== ""
      ? objective
      : plan?.research_objective_snapshot ?? "";

  const coverage = useQuery({
    queryKey: ["research-plan-coverage", activeProjectId, plan?.version],
    queryFn: () => getResearchPlanCoverage(activeProjectId!),
    enabled: Boolean(activeProjectId && plan),
    staleTime: 10_000,
  });

  const validate = useMutation({
    mutationFn: () => validateResearchPlan(activeProjectId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["research-plan-versions", activeProjectId],
      });
    },
  });

  const save = useMutation({
    mutationFn: () =>
      saveResearchPlanRevision(activeProjectId!, {
        researchObjectiveSnapshot: planObjective || null,
        planningMode: plan?.planning_mode ?? null,
      }),
    onSuccess: async () => {
      setObjective("");
      await queryClient.invalidateQueries({
        queryKey: ["research-plan-versions", activeProjectId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["research-plan-coverage", activeProjectId],
      });
    },
  });

  const generate = useMutation({
    mutationFn: () => generateResearchPlan(activeProjectId!, false),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["research-plan-versions", activeProjectId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["research-plan-coverage", activeProjectId],
      });
    },
  });

  const errors = [
    workspaces.error,
    projects.error,
    versions.error,
    coverage.error,
    validate.error,
    save.error,
    generate.error,
  ].filter(Boolean);

  if (errors.length > 0) {
    return (
      <section className="card pad" role="alert">
        <h2>Research plan unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {(errors[0] as Error).message}
        </p>
        <button className="btn" style={{ marginTop: 14 }} onClick={() => {
          void workspaces.refetch();
          void projects.refetch();
          void versions.refetch();
        }}>
          Retry
        </button>
      </section>
    );
  }

  const sections = plan?.sections ?? [];
  const requirements = plan?.evidence_requirements ?? [];
  const questions = Array.isArray(plan?.research_questions_snapshot)
    ? plan?.research_questions_snapshot
    : [];
  const hypotheses = Array.isArray(plan?.hypotheses_snapshot)
    ? plan?.hypotheses_snapshot
    : [];

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Planning</div>
            <h2 style={{ marginTop: 4 }}>Research plan</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              The current plan is loaded from the project planning API.
            </p>
          </div>
          <span className="tag">
            {plan ? "Version " + plan.version : "No plan"}
          </span>
        </div>

        <div className="grid grid-2" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="plan-workspace">Workspace</label>
            <select
              id="plan-workspace"
              className="input"
              value={activeWorkspaceId ?? ""}
              onChange={(event) => {
                setWorkspaceId(event.target.value);
                setProjectId(undefined);
              }}
            >
              {(workspaces.data ?? []).map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="plan-project">Project</label>
            <select
              id="plan-project"
              className="input"
              value={activeProjectId ?? ""}
              onChange={(event) => {
                setProjectId(event.target.value);
                setObjective("");
              }}
              disabled={projects.isPending}
            >
              {(projects.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {activeProjectId && !plan && !versions.isPending && (
          <div className="empty" style={{ marginTop: 14 }}>
            <div className="big">∅</div>
            <div>No research plan exists for this project yet.</div>
            <button
              className="btn primary"
              style={{ marginTop: 12 }}
              disabled={generate.isPending}
              onClick={() => generate.mutate()}
            >
              {generate.isPending ? "Generating…" : "Generate plan"}
            </button>
          </div>
        )}
      </section>

      {plan && (
        <>
          <section className="grid grid-3">
            <div className="card metric">
              <div className="label">Completeness</div>
              <div className="value">
                {Math.round((plan.completeness_score ?? 0) * 100)}%
              </div>
              <div className="delta">{plan.validation_status}</div>
            </div>
            <div className="card metric">
              <div className="label">Evidence coverage</div>
              <div className="value">
                {Math.round(
                  (coverage.data?.coverage_score ??
                    plan.coverage_score ??
                    0) * 100,
                )}%
              </div>
              <div className="delta">
                {coverage.data?.coverage_state ?? "Plan coverage"}
              </div>
            </div>
            <div className="card metric">
              <div className="label">Sections</div>
              <div className="value">{sections.length}</div>
              <div className="delta">
                {requirements.length} evidence requirements
              </div>
            </div>
          </section>

          <section className="grid grid-2">
            <section className="card pad">
              <h3>Research objective</h3>
              <textarea
                aria-label="Research objective"
                className="input textarea"
                style={{ marginTop: 10 }}
                value={planObjective}
                onChange={(event) => setObjective(event.target.value)}
              />
              <div className="actions" style={{ marginTop: 12 }}>
                <button
                  className="btn"
                  disabled={save.isPending || !activeProjectId}
                  onClick={() => save.mutate()}
                >
                  {save.isPending ? "Saving…" : "Save revision"}
                </button>
                <button
                  className="btn primary"
                  disabled={validate.isPending}
                  onClick={() => validate.mutate()}
                >
                  {validate.isPending ? "Validating…" : "Validate"}
                </button>
                <button
                  className="btn"
                  disabled={generate.isPending}
                  onClick={() => generate.mutate()}
                >
                  {generate.isPending ? "Generating…" : "Regenerate"}
                </button>
              </div>
              {(validate.data || plan.validation_errors?.length) && (
                <div className="muted small" style={{ marginTop: 10 }}>
                  Validation:{" "}
                  {validate.data?.validation_status ??
                    plan.validation_status}{" "}
                  · completeness{" "}
                  {Math.round(
                    (validate.data?.completeness_score ??
                      plan.completeness_score ??
                      0) * 100,
                  )}%
                </div>
              )}
            </section>

            <section className="card pad">
              <h3>Plan metadata</h3>
              <div className="stack" style={{ marginTop: 12 }}>
                <div className="row">
                  <span className="muted">Planning mode</span>
                  <b>{plan.planning_mode || "n/a"}</b>
                </div>
                <div className="row">
                  <span className="muted">Planner version</span>
                  <b>{plan.planner_version}</b>
                </div>
                <div className="row">
                  <span className="muted">Paper type</span>
                  <b>{plan.paper_type_code ?? "n/a"}</b>
                </div>
                <div className="row">
                  <span className="muted">Research design</span>
                  <b>{plan.research_design_code ?? "n/a"}</b>
                </div>
              </div>
            </section>
          </section>

          <section className="grid grid-2">
            <section className="card pad">
              <div className="row">
                <h3>Manuscript outline</h3>
                <span className="tag">{sections.length} sections</span>
              </div>
              <div className="list" style={{ marginTop: 12 }}>
                {sections.map((section) => (
                  <div className="list-item" key={section.id}>
                    <div className="row">
                      <div>
                        <div className="title">
                          {section.display_order}. {section.title}
                        </div>
                        <div className="meta">
                          {section.section_type} · {section.word_budget} words ·{" "}
                          target {Math.round(section.evidence_coverage_target * 100)}%
                        </div>
                      </div>
                      <span className="tag">{section.status}</span>
                    </div>
                    {section.purpose && (
                      <div className="muted small" style={{ marginTop: 6 }}>
                        {section.purpose}
                      </div>
                    )}
                  </div>
                ))}
                {sections.length === 0 && (
                  <div className="empty">
                    <div className="big">∅</div>
                    <div>No sections are defined in this plan.</div>
                  </div>
                )}
              </div>
            </section>

            <section className="card pad">
              <h3>Research inputs</h3>
              <div className="stack" style={{ marginTop: 12 }}>
                <div>
                  <div className="muted small">Research questions</div>
                  <div style={{ marginTop: 6 }}>
                    {questions.length
                      ? questions.map((question, index) => (
                          <div className="list-item" key={index}>
                            {typeof question === "string"
                              ? question
                              : JSON.stringify(question)}
                          </div>
                        ))
                      : "None recorded in the current plan."}
                  </div>
                </div>
                <div>
                  <div className="muted small">Hypotheses</div>
                  <div style={{ marginTop: 6 }}>
                    {hypotheses.length
                      ? hypotheses.map((hypothesis, index) => (
                          <div className="list-item" key={index}>
                            {typeof hypothesis === "string"
                              ? hypothesis
                              : JSON.stringify(hypothesis)}
                          </div>
                        ))
                      : "None recorded in the current plan."}
                  </div>
                </div>
              </div>
            </section>
          </section>

          <section className="card pad">
            <div className="row">
              <h3>Evidence requirements</h3>
              <span className="tag">{requirements.length}</span>
            </div>
            <div className="list" style={{ marginTop: 12 }}>
              {requirements.map((requirement) => (
                <div className="list-item" key={requirement.id}>
                  <div className="row">
                    <div>
                      <div className="title">{requirement.requirement_key}</div>
                      <div className="meta">
                        {requirement.requirement_type} ·{" "}
                        {requirement.required ? "required" : "optional"} ·{" "}
                        priority {requirement.priority}
                      </div>
                    </div>
                    <span className="tag">
                      {Math.round(requirement.coverage_weight * 100)}% weight
                    </span>
                  </div>
                  <div className="muted small" style={{ marginTop: 6 }}>
                    {requirement.description}
                  </div>
                </div>
              ))}
              {requirements.length === 0 && (
                <div className="empty">
                  <div className="big">∅</div>
                  <div>No evidence requirements are attached to this plan.</div>
                </div>
              )}
            </div>
          </section>
        </>
      )}

      {!activeProjectId && !projects.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>Create a project in Workspace before building a research plan.</div>
        </section>
      )}
    </div>
  );
}
