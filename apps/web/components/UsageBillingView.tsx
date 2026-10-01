"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  changeSubscription,
  createWorkspaceCheckout,
  getWorkspacePlan,
  getWorkspaceSubscription,
  getWorkspaceUsage,
  listBillingPlans,
  switchWorkspacePlan,
  type Plan,
  type Subscription,
} from "@/lib/api/billing";
import { useResearchContext } from "@/lib/research-context";
import { queryKeys } from "@/lib/query-keys";

function formatBytes(value: number): string {
  if (value < 1024) return value + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value;
  let unit = "B";
  for (const next of units) {
    amount /= 1024; unit = next;
    if (amount < 1024) break;
  }
  return amount.toFixed(amount >= 10 ? 0 : 1) + " " + unit;
}
function formatDate(value: string | null): string {
  if (!value) return "Not set";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}
function featureLabel(metric: string): string {
  const labels: Record<string, string> = {
    "projects.max": "Projects", "reports.monthly": "Reports this month", "members.max": "Members",
    "storage.bytes": "Storage", ai_generation_units: "AI generation units", "search.requests": "Search requests",
  };
  return labels[metric] ?? metric;
}
function displayValue(value: number, unit: string): string {
  return unit === "bytes" ? formatBytes(value) : value.toLocaleString();
}

export function UsageBillingView() {
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const {
    workspaceId: contextWorkspaceId,
    workspace: selectedWorkspace,
    workspacesQuery,
  } = useResearchContext();
  const workspaces = workspacesQuery.data ?? [];
  const workspaceId = contextWorkspaceId ?? "";

  const plansQuery = useQuery({
    queryKey: queryKeys.billingPlans,
    queryFn: listBillingPlans,
    enabled: Boolean(workspaceId),
  });
  const usageQuery = useQuery({
    queryKey: queryKeys.workspaceUsage(workspaceId),
    queryFn: () => getWorkspaceUsage(workspaceId),
    enabled: Boolean(workspaceId),
  });
  const planQuery = useQuery({
    queryKey: queryKeys.workspacePlan(workspaceId),
    queryFn: () => getWorkspacePlan(workspaceId),
    enabled: Boolean(workspaceId),
  });
  const subscriptionQuery = useQuery({
    queryKey: queryKeys.workspaceSubscription(workspaceId),
    queryFn: () => getWorkspaceSubscription(workspaceId),
    enabled: Boolean(workspaceId),
  });

  const detailsError = [workspacesQuery, plansQuery, usageQuery, planQuery, subscriptionQuery]
    .map((query) => query.error)
    .find((value): value is Error => value instanceof Error);
  const usage = usageQuery.data ?? null;
  const currentPlan = planQuery.data ?? null;
  const subscription: Subscription | null = subscriptionQuery.data ?? null;

  const busyPlan = useMutation({
    mutationFn: async (plan: Plan) =>
      switchWorkspacePlan(workspaceId, plan.code),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workspaceUsage(workspaceId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workspacePlan(workspaceId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workspaceSubscription(workspaceId) }),
      ]);
    },
  });

  const checkout = useMutation({
    mutationFn: async (plan: Plan) =>
      createWorkspaceCheckout(workspaceId, plan.code),
    onSuccess: (result) => {
      if (result.checkout_url) window.location.assign(result.checkout_url);
    },
  });

  const subscriptionAction = useMutation({
    mutationFn: async (action: "cancel" | "resume") =>
      changeSubscription(workspaceId, action),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaceSubscription(workspaceId) });
    },
  });

  const firstError = error || (detailsError instanceof Error ? detailsError.message : null) ||
    (busyPlan.error instanceof Error ? busyPlan.error.message : null) ||
    (checkout.error instanceof Error ? checkout.error.message : null) ||
    (subscriptionAction.error instanceof Error ? subscriptionAction.error.message : null);

  if (workspacesQuery.isPending) {
    return <section className="card pad" aria-busy="true"><h2>Loading billing workspace…</h2><p className="muted">Reading workspaces and current billing data.</p></section>;
  }
  if (workspaces.length === 0) {
    return <section className="card pad"><h2>No workspace available</h2><p className="muted">Create a workspace before viewing usage and billing.</p></section>;
  }

  const isOwner = selectedWorkspace?.role === "owner";
  const plans = plansQuery.data ?? [];

  return (
    <>
      <div className="page-head">
        <div><div className="eyebrow">Workspace plan</div><h1>Usage & billing</h1><p>Live workspace usage, plan entitlements and subscription state.</p></div>
      </div>

      {firstError && (
        <section className="card pad" role="alert" style={{ marginBottom: 16 }}>
          <div className="row"><div><h3>Billing request failed</h3><p className="muted small">{firstError}</p></div><button className="btn" type="button" onClick={() => setError(null)}>Dismiss</button></div>
        </section>
      )}

      <div className="grid grid-2">
        <section className="card pad">
          <div className="row"><div><h3>Current subscription</h3><div className="muted small">Source: {subscription?.provider ?? "local workspace state"}</div></div><span className="tag">{subscription?.status ?? "No active subscription"}</span></div>
          <div style={{ marginTop: 16 }}><div className="eyebrow">Plan</div><div style={{ fontSize: 32, fontWeight: 800, marginTop: 4 }}>{currentPlan?.name ?? subscription?.plan_code ?? "Unknown"}</div><p className="muted small">{currentPlan?.description ?? "No plan description is available."}</p></div>
          <div className="grid grid-2" style={{ marginTop: 16 }}>
            <div><div className="small muted">Current period</div><b>{formatDate(subscription?.current_period_start ?? usage?.period_start ?? null)}{" → "}{formatDate(subscription?.current_period_end ?? usage?.period_end ?? null)}</b></div>
            <div><div className="small muted">Cancellation</div><b>{subscription?.cancel_at_period_end ? "At period end" : "Not scheduled"}</b></div>
          </div>
          {isOwner && subscription && (
            <div className="actions" style={{ marginTop: 18 }}>
              {subscription.cancel_at_period_end ? (
                <button className="btn primary" type="button" disabled={subscriptionAction.isPending} onClick={() => subscriptionAction.mutate("resume")}>{subscriptionAction.isPending ? "Saving…" : "Resume subscription"}</button>
              ) : (
                <button className="btn" type="button" disabled={subscriptionAction.isPending} onClick={() => subscriptionAction.mutate("cancel")}>{subscriptionAction.isPending ? "Saving…" : "Cancel at period end"}</button>
              )}
            </div>
          )}
        </section>

        <section className="card pad">
          <div className="row"><div><h3>Usage this period</h3><div className="muted small">{usage ? formatDate(usage.period_start) + " → " + formatDate(usage.period_end) : "Usage data unavailable"}</div></div>{(usageQuery.isFetching || planQuery.isFetching || subscriptionQuery.isFetching) && <span className="tag">Refreshing…</span>}</div>
          <div className="stack" style={{ marginTop: 16 }}>
            {(usage?.items ?? []).map((item) => {
              const percent = item.limit && item.limit > 0 ? Math.min(100, (item.current / item.limit) * 100) : null;
              return <div key={item.metric}><div className="row small"><span>{featureLabel(item.metric)}</span><span><b>{displayValue(item.current, item.unit)}</b>{item.limit !== null ? " / " + displayValue(item.limit, item.unit) : " / unlimited"}</span></div>{percent !== null && <div className="progress" style={{ marginTop: 7 }}><span style={{ width: percent + "%" }} /></div>}</div>;
            })}
            {(usage?.items ?? []).length === 0 && <p className="muted small">No usage metrics are available for this workspace.</p>}
          </div>
        </section>
      </div>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row"><div><h3>Available plans</h3><div className="muted small">Plans come from the active billing catalog.</div></div>{!isOwner && <span className="tag">Owner access required to change plan</span>}</div>
        <div className="grid grid-3" style={{ marginTop: 16 }}>
          {plans.map((plan) => {
            const isCurrent = plan.code === currentPlan?.code;
            return <article className="card pad" key={plan.id}>
              <div className="row"><div><div className="eyebrow">{plan.code}</div><h3 style={{ marginTop: 4 }}>{plan.name}</h3></div>{isCurrent && <span className="tag success">Current</span>}</div>
              <p className="muted small" style={{ minHeight: 42 }}>{plan.description ?? "No description provided."}</p>
              {isCurrent ? <button className="btn" type="button" disabled>Current plan</button> : <div className="actions">
                <button className="btn primary" type="button" disabled={!isOwner || busyPlan.isPending || checkout.isPending} onClick={() => busyPlan.mutate(plan)}>{busyPlan.isPending && busyPlan.variables?.id === plan.id ? "Switching…" : "Switch plan"}</button>
                <button className="btn" type="button" disabled={!isOwner || busyPlan.isPending || checkout.isPending} onClick={() => checkout.mutate(plan)}>{checkout.isPending && checkout.variables?.id === plan.id ? "Opening…" : "Checkout"}</button>
              </div>}
            </article>;
          })}
        </div>
      </section>

      <section className="card pad" style={{ marginTop: 16 }}>
        <h3>Billing records</h3>
        <p className="muted small">Invoice history and downloadable invoice files are not exposed by the current backend contract, so no synthetic invoice rows are shown here.</p>
      </section>
    </>
  );
}
