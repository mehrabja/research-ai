"use client";

import Link from "next/link";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";
import {
  api,
} from "@/lib/api/client";
import {
  useWorkspace,
} from "@/components/app-shell";

export default function Dashboard() {
  const {
    workspaceId,
    workspaces,
  } = useWorkspace();

  const queryClient =
    useQueryClient();

  const [name, setName] =
    useState("");

  const projects = useQuery({
    queryKey: [
      "projects",
      workspaceId,
    ],
    queryFn: () =>
      api.projects(
        workspaceId!,
      ),
    enabled: !!workspaceId,
  });

  const reports = useQuery({
    queryKey: [
      "reports",
      workspaceId,
    ],
    queryFn: () =>
      api.reports(
        workspaceId!,
      ),
    enabled: !!workspaceId,
  });

  const usage = useQuery({
    queryKey: [
      "usage",
      workspaceId,
    ],
    queryFn: () =>
      api.usage(
        workspaceId!,
      ),
    enabled: !!workspaceId,
  });

  const jobs = useQuery({
    queryKey: [
      "jobs",
      workspaceId,
    ],
    queryFn: api.jobs,
    enabled: !!workspaceId,
  });

  const createWorkspace =
    useMutation({
      mutationFn: () =>
        api.createWorkspace(
          name.trim(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries(
          {
            queryKey: [
              "workspaces",
            ],
          },
        );

        setName("");
      },
    });

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  const projectItems =
    projects.data?.items ?? [];

  const reportItems =
    reports.data ?? [];

  const usageItems =
    usage.data?.items ?? [];

  const limitedUsage =
    usageItems.filter(
      (item) =>
        item.limit !== null,
    );

  const activeJobs =
    (jobs.data ?? []).filter(
      (job) =>
        ![
          "completed",
          "succeeded",
          "failed",
          "cancelled",
        ].includes(
          job.status.toLowerCase(),
        ),
    );

  const recentReports =
    [...reportItems]
      .sort(
        (a, b) =>
          new Date(
            b.updated_at,
          ).getTime() -
          new Date(
            a.updated_at,
          ).getTime(),
      )
      .slice(0, 6);

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Workspace control plane
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Research AI
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Projects, reports, research intelligence,
          durable jobs, and workspace consumption in one
          operational view.
        </p>
      </header>

      <div className="grid md:grid-cols-4 gap-4">
        <Metric
          label="Projects"
          value={
            projects.data?.total ??
            "—"
          }
        />

        <Metric
          label="Reports"
          value={
            reportItems.length
          }
        />

        <Metric
          label="Active jobs"
          value={
            jobs.isPending
              ? "—"
              : activeJobs.length
          }
        />

        <Metric
          label="Workspaces"
          value={
            workspaces.length
          }
        />
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <section className="card p-5 xl:col-span-2">
          <div className="flex flex-wrap justify-between gap-4">
            <div>
              <h2 className="font-semibold">
                Projects
              </h2>

              <p className="muted text-sm mt-1">
                Current workspace inventory.
              </p>
            </div>

            <Link
              href="/projects"
              className="btn btn-secondary text-sm"
            >
              Open projects
            </Link>
          </div>

          <div className="mt-4 divide-y">
            {projects.isPending && (
              <div className="py-6 muted">
                Loading projects…
              </div>
            )}

            {!projects.isPending &&
              !projectItems.length && (
                <div className="py-7 muted text-sm">
                  No projects yet.
                </div>
              )}

            {projectItems
              .slice(0, 8)
              .map((project) => (
                <Link
                  key={project.id}
                  href={
                    "/projects/" +
                    project.id
                  }
                  className="flex justify-between gap-4 py-4"
                >
                  <div className="min-w-0">
                    <div className="font-medium truncate">
                      {project.name}
                    </div>

                    <div className="muted text-sm mt-1">
                      {project.domain ||
                        "No domain"}{" "}
                      ·{" "}
                      {
                        project.report_count
                      }{" "}
                      reports
                    </div>
                  </div>

                  <span className="muted text-sm shrink-0">
                    {project.status}
                  </span>
                </Link>
              ))}
          </div>
        </section>

        <section className="card p-5">
          <div className="flex justify-between gap-3">
            <div>
              <h2 className="font-semibold">
                Jobs
              </h2>

              <p className="muted text-sm mt-1">
                Durable processing state.
              </p>
            </div>

            <Link
              href="/jobs"
              className="muted text-sm"
            >
              View all
            </Link>
          </div>

          <div className="mt-4 space-y-3">
            {jobs.isPending && (
              <div className="muted text-sm">
                Loading jobs…
              </div>
            )}

            {!jobs.isPending &&
              !activeJobs.length && (
                <div className="muted text-sm">
                  No active jobs.
                </div>
              )}

            {activeJobs
              .slice(0, 5)
              .map((job) => (
                <div
                  key={job.id}
                  className="rounded-xl border p-3"
                  style={{
                    borderColor:
                      "var(--line)",
                  }}
                >
                  <div className="font-medium text-sm">
                    {job.job_type}
                  </div>

                  <div className="muted text-xs mt-1">
                    {job.status} ·{" "}
                    {
                      job.attempt_count
                    }
                    /
                    {
                      job.max_attempts
                    }
                  </div>
                </div>
              ))}
          </div>
        </section>
      </div>

      <section className="card p-5">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <h2 className="font-semibold">
              Recent reports
            </h2>

            <p className="muted text-sm mt-1">
              Latest report activity in the current
              workspace.
            </p>
          </div>

          <Link
            href="/projects"
            className="btn btn-secondary text-sm"
          >
            Projects
          </Link>
        </div>

        <div className="mt-4 grid md:grid-cols-2 gap-3">
          {recentReports.map(
            (report) => (
              <Link
                key={report.id}
                href={
                  "/reports/" +
                  report.id
                }
                className="rounded-xl border p-4"
                style={{
                  borderColor:
                    "var(--line)",
                }}
              >
                <div className="flex justify-between gap-3">
                  <div className="font-medium truncate">
                    {report.topic}
                  </div>

                  <span className="muted text-xs shrink-0">
                    {report.status}
                  </span>
                </div>

                <div className="muted text-sm mt-2">
                  {report.domain ||
                    "No domain"}{" "}
                  ·{" "}
                  {
                    report.output_language
                  }
                </div>

                <div className="muted text-xs mt-2">
                  Updated{" "}
                  {new Date(
                    report.updated_at,
                  ).toLocaleString()}
                </div>
              </Link>
            ),
          )}

          {!reports.isPending &&
            !recentReports.length && (
              <div className="md:col-span-2 muted text-sm py-5">
                No reports available yet.
              </div>
            )}
        </div>
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <h2 className="font-semibold">
              Usage
            </h2>

            <p className="muted text-sm mt-1">
              Current workspace consumption and configured
              entitlement limits.
            </p>
          </div>

          <Link
            href="/usage"
            className="muted text-sm"
          >
            Full usage
          </Link>
        </div>

        <div className="mt-5 grid md:grid-cols-2 gap-5">
          {usageItems
            .slice(0, 8)
            .map((item) => {
              const percentage =
                item.limit !== null &&
                item.limit > 0
                  ? Math.min(
                      100,
                      (item.current /
                        item.limit) *
                        100,
                    )
                  : null;

              return (
                <div
                  key={item.metric}
                >
                  <div className="flex justify-between gap-3 text-sm">
                    <span className="truncate">
                      {item.metric}
                    </span>

                    <span className="muted shrink-0">
                      {item.current}
                      {item.limit !==
                        null &&
                        " / " +
                          item.limit}
                    </span>
                  </div>

                  {percentage !==
                    null && (
                    <div className="h-2 mt-2 rounded-full bg-white/8 overflow-hidden">
                      <div
                        className="h-full"
                        style={{
                          width:
                            percentage +
                            "%",
                        }}
                      />
                    </div>
                  )}

                  <div className="muted text-xs mt-1">
                    {item.unit}
                    {percentage !==
                      null &&
                      " · " +
                        percentage.toFixed(
                          1,
                        ) +
                        "% used"}
                  </div>
                </div>
              );
            })}

          {!usage.isPending &&
            !usageItems.length && (
              <div className="md:col-span-2 muted text-sm">
                No usage metrics are currently reported.
              </div>
            )}
        </div>

        {limitedUsage.length >
          8 && (
          <div className="muted text-xs mt-4">
            Showing the first 8 metrics ·{" "}
            {limitedUsage.length} limited
            metrics reported.
          </div>
        )}
      </section>

      <section className="card p-5">
        <div>
          <h2 className="font-semibold">
            Create workspace
          </h2>

          <p className="muted text-sm mt-1">
            Add another workspace to your account.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <input
            className="input"
            value={name}
            onChange={(event) =>
              setName(
                event.target.value,
              )
            }
            placeholder="Workspace name"
          />

          <button
            className="btn btn-primary"
            disabled={
              !name.trim() ||
              createWorkspace.isPending
            }
            onClick={() =>
              createWorkspace.mutate()
            }
          >
            {createWorkspace.isPending
              ? "Creating…"
              : "Create"}
          </button>
        </div>

        {createWorkspace.error && (
          <div
            className="text-sm mt-3"
            style={{
              color:
                "var(--danger)",
            }}
          >
            {
              createWorkspace.error
                .message
            }
          </div>
        )}

        {createWorkspace.data && (
          <div className="muted text-sm mt-3">
            Workspace created:{" "}
            {createWorkspace.data.name}
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
  value: string | number;
}) {
  return (
    <div className="card p-5">
      <div className="muted text-sm">
        {label}
      </div>

      <div className="text-3xl font-semibold mt-2">
        {value}
      </div>
    </div>
  );
}