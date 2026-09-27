"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

const sections = [
  ["research", "Research"],
  ["sources", "Sources"],
  ["evidence", "Evidence"],
  ["literature", "Literature"],
  ["planning", "Planning"],
  ["knowledge-graph", "Knowledge Graph"],
  ["manuscript", "Manuscript"],
  ["human-review", "Human Review"],
  ["translation", "Translation"],
  ["files", "Files"],
  ["jobs", "Jobs"],
  ["collaboration", "Collaboration"],
  ["usage", "Usage"],
  ["billing", "Billing"],
  ["settings", "Settings"],
] as const;

type Props = {
  title: string;
  description: string;
  active?: string;
};

export function WorkspaceFeaturePage({ title, description, active }: Props) {
  const { workspaceId } = useWorkspace();
  const usage = useQuery({
    queryKey: ["usage", workspaceId],
    queryFn: () => api.usage(workspaceId!),
    enabled: !!workspaceId,
  });
  const notifications = useQuery({
    queryKey: ["notifications", workspaceId],
    queryFn: () => api.notifications(workspaceId!),
    enabled: !!workspaceId,
  });

  if (!workspaceId) {
    return <div className="card p-6 muted">Loading workspace…</div>;
  }

  const projectMetric = usage.data?.items.find((x) => x.metric === "projects.max");
  const aiMetric = usage.data?.items.find((x) => x.metric === "ai_generation_units");

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">Workspace</div>
        <div className="flex items-start justify-between gap-5 mt-2">
          <div>
            <h1 className="text-3xl font-semibold">{title}</h1>
            <p className="muted mt-2 max-w-3xl">{description}</p>
          </div>
          <Link href="/dashboard" className="btn btn-secondary text-sm">Dashboard</Link>
        </div>
      </header>

      <nav className="flex flex-wrap gap-2">
        {sections.map(([key, label]) => (
          <Link
            key={key}
            href={"/" + (key === "settings" ? "settings" : key)}
            className={"btn text-sm " + (active === key ? "btn-primary" : "btn-secondary")}
          >
            {label}
          </Link>
        ))}
      </nav>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="card p-5">
          <div className="muted text-sm">Workspace ID</div>
          <div className="font-mono text-xs mt-2 break-all">{workspaceId}</div>
        </div>
        <div className="card p-5">
          <div className="muted text-sm">Projects</div>
          <div className="text-2xl font-semibold mt-2">
            {projectMetric?.current ?? "—"}{projectMetric?.limit == null ? "" : " / " + projectMetric.limit}
          </div>
        </div>
        <div className="card p-5">
          <div className="muted text-sm">AI generation units</div>
          <div className="text-2xl font-semibold mt-2">
            {aiMetric?.current ?? "—"}{aiMetric?.limit == null ? "" : " / " + aiMetric.limit}
          </div>
        </div>
      </div>

      <section className="card p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-semibold">Live workspace activity</h2>
            <p className="muted text-sm mt-1">Data is loaded from the backend workspace contract.</p>
          </div>
          <span className="muted text-xs">{notifications.data?.unread ?? 0} unread notifications</span>
        </div>
        <div className="mt-5 divide-y" style={{ borderColor: "var(--line)" }}>
          {(notifications.data?.items ?? []).slice(0, 8).map((item) => (
            <div key={item.id} className="py-4">
              <div className="font-medium">{item.title}</div>
              <div className="muted text-sm mt-1">{item.body}</div>
            </div>
          ))}
          {notifications.isPending && <div className="py-6 muted text-sm">Loading activity…</div>}
          {!notifications.isPending && notifications.data?.items.length === 0 && (
            <div className="py-6 muted text-sm">No notifications recorded for this workspace.</div>
          )}
        </div>
      </section>
    </div>
  );
}
