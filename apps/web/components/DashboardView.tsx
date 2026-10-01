"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { listNotifications } from "@/lib/api/notifications";
import { getWorkspaceUsage } from "@/lib/api/billing";
import { queryKeys } from "@/lib/query-keys";
import { useResearchContext } from "@/lib/research-context";

function formatBytes(value: number): string {
  if (value < 1024) return value + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value;
  let unit = "B";
  for (const next of units) {
    amount /= 1024;
    unit = next;
    if (amount < 1024) break;
  }
  return amount.toFixed(amount >= 10 ? 0 : 1) + " " + unit;
}

function usageLabel(metric: string): string {
  const labels: Record<string, string> = {
    ai_generation_units: "AI generation units",
    "storage.bytes": "Storage",
    "search.requests": "Search requests",
    "reports.monthly": "Reports this month",
  };
  return labels[metric] ?? metric;
}

export default function DashboardView() {
  const { user, workspace, workspaceId, projectsQuery, contextHref } =
    useResearchContext();
  const projects = projectsQuery.data ?? [];

  const notificationsQuery = useQuery({
    queryKey: queryKeys.notifications(50),
    queryFn: () => listNotifications(workspaceId ?? undefined),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
  });

  const usageQuery = useQuery({
    queryKey: queryKeys.workspaceUsage(workspaceId ?? ""),
    queryFn: () => getWorkspaceUsage(workspaceId!),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
  });

  if (
    projectsQuery.isPending ||
    notificationsQuery.isPending ||
    usageQuery.isPending
  ) {
    return (
      <section className="card pad" aria-busy="true">
        <div className="eyebrow">Research AI</div>
        <h1>Loading dashboard…</h1>
        <p className="muted">
          Reading workspace projects, activity and usage.
        </p>
      </section>
    );
  }

  if (projectsQuery.error || notificationsQuery.error || usageQuery.error) {
    const error =
      projectsQuery.error ?? notificationsQuery.error ?? usageQuery.error;
    return (
      <section className="card pad" role="alert">
        <div className="eyebrow">Dashboard</div>
        <h1>Dashboard data is unavailable</h1>
        <p className="muted">
          {error instanceof Error
            ? error.message
            : "Unable to load dashboard data."}
        </p>
      </section>
    );
  }

  const reportCount = projects.reduce(
    (total, project) => total + project.report_count,
    0,
  );
  const usage = usageQuery.data;
  const storage =
    usage?.items.find((item) => item.metric === "storage.bytes") ?? null;
  const aiUnits =
    usage?.items.find((item) => item.metric === "ai_generation_units") ?? null;
  const notifications = notificationsQuery.data?.items ?? [];
  const unread = notificationsQuery.data?.unread ?? 0;
  const visibleProjects = projects.slice(0, 3);
  const displayName = user.full_name?.trim() || user.email;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Dashboard</div>
          <h1>Research overview</h1>
          <p>
            {displayName} · {workspace?.name ?? "Current workspace"}
          </p>
        </div>
        <div className="actions">
          <Link className="btn" href={contextHref("/team")}>
            Invite teammate
          </Link>
          <Link className="btn primary" href={contextHref("/workspace")}>
            Manage workspace
          </Link>
        </div>
      </div>

      <div className="grid grid-4">
        <div className="card metric">
          <div className="label">Active projects</div>
          <div className="value">{projects.length}</div>
          <div className="delta">Live workspace records</div>
        </div>
        <div className="card metric">
          <div className="label">Reports</div>
          <div className="value">{reportCount}</div>
          <div className="delta">Across active projects</div>
        </div>
        <div className="card metric">
          <div className="label">Unread activity</div>
          <div className="value">{unread}</div>
          <div className="delta">
            {unread === 0
              ? "All caught up"
              : "Notifications need review"}
          </div>
        </div>
        <div className="card metric">
          <div className="label">
            {storage ? usageLabel(storage.metric) : "AI usage"}
          </div>
          <div className="value">
            {storage
              ? formatBytes(storage.current)
              : aiUnits
                ? aiUnits.current.toLocaleString()
                : "—"}
          </div>
          <div className="delta">
            {storage?.limit !== null && storage?.limit !== undefined
              ? formatBytes(storage.limit) + " limit"
              : aiUnits?.limit !== null && aiUnits?.limit !== undefined
                ? aiUnits.limit.toLocaleString() + " limit"
                : "No limit reported"}
          </div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <section className="card pad">
          <div className="row">
            <div>
              <h3>Projects</h3>
              <div className="muted small">
                Real projects in the selected workspace
              </div>
            </div>
            <Link className="btn ghost" href={contextHref("/workspace")}>
              View all
            </Link>
          </div>
          <div className="list">
            {visibleProjects.map((project) => (
              <article className="list-item" key={project.id}>
                <div className="row">
                  <div style={{ minWidth: 0 }}>
                    <div className="title">{project.name}</div>
                    <div className="meta">
                      {project.status} · {project.report_count} reports
                      {project.domain ? " · " + project.domain : ""}
                    </div>
                  </div>
                  <Link
                    className="btn"
                    href={contextHref(
                      "/research?projectId=" + project.id,
                    )}
                  >
                    Open
                  </Link>
                </div>
              </article>
            ))}
            {visibleProjects.length === 0 && (
              <div className="empty">
                <div className="big">∅</div>
                <div>No projects yet.</div>
                <Link
                  className="btn primary"
                  style={{ marginTop: 12 }}
                  href={contextHref("/workspace")}
                >
                  Create project
                </Link>
              </div>
            )}
          </div>
        </section>

        <section className="card pad">
          <div className="row">
            <div>
              <h3>Recent activity</h3>
              <div className="muted small">Workspace notifications</div>
            </div>
            <Link
              className="btn ghost"
              href={contextHref("/settings?tab=notifications")}
            >
              Notifications
            </Link>
          </div>
          <div className="list">
            {notifications.slice(0, 4).map((notification) => (
              <article className="list-item" key={notification.id}>
                <div className="row">
                  <div style={{ minWidth: 0 }}>
                    <div className="title">{notification.title}</div>
                    <div className="meta">{notification.message}</div>
                  </div>
                  <span
                    className={"tag " + (notification.read_at ? "" : "warn")}
                  >
                    {notification.read_at ? "Read" : "New"}
                  </span>
                </div>
              </article>
            ))}
            {notifications.length === 0 && (
              <div className="empty">No workspace activity yet.</div>
            )}
          </div>
        </section>
      </div>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row">
          <div>
            <h3>Current workspace usage</h3>
            <div className="muted small">
              Live entitlement consumption for this billing period
            </div>
          </div>
          <Link className="btn" href={contextHref("/usage-billing")}>
            View usage & billing
          </Link>
        </div>
        <div className="grid grid-3" style={{ marginTop: 16 }}>
          {(usage?.items ?? []).slice(0, 3).map((item) => {
            const percent =
              item.limit && item.limit > 0
                ? Math.min(100, (item.current / item.limit) * 100)
                : null;
            const current =
              item.unit === "bytes"
                ? formatBytes(item.current)
                : item.current.toLocaleString();
            const limit =
              item.limit === null
                ? "unlimited"
                : item.unit === "bytes"
                  ? formatBytes(item.limit)
                  : item.limit.toLocaleString();
            return (
              <div key={item.metric}>
                <div className="row small">
                  <span>{usageLabel(item.metric)}</span>
                  <span>
                    <b>{current}</b> / {limit}
                  </span>
                </div>
                {percent !== null && (
                  <div className="progress" style={{ marginTop: 7 }}>
                    <span style={{ width: percent + "%" }} />
                  </div>
                )}
              </div>
            );
          })}
          {(usage?.items ?? []).length === 0 && (
            <p className="muted small">No usage metrics are available.</p>
          )}
        </div>
      </section>
    </>
  );
}
