"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { listWorkspaces, type Workspace } from "@/lib/api/workspaces";

type Plan = { id: string; code: string; name: string; description: string | null };
type Entitlement = { feature: string; limit_value: number | null; unit: string };
type WorkspacePlan = Plan & { entitlements: Entitlement[] };
type UsageItem = { metric: string; current: number; limit: number | null; unit: string };
type UsageResponse = { workspace_id: string; period_start: string; period_end: string; items: UsageItem[] };
type Subscription = {
  id: string;
  workspace_id: string;
  plan_id: string;
  plan_code: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  provider: string;
  cancel_at_period_end: boolean;
  created_at: string;
};

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try { payload = JSON.parse(text) as unknown; } catch { payload = null; }
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && payload !== null && "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "Request failed (" + response.status + ")";
    throw new Error(detail);
  }
  return payload as T;
}

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

function formatDate(value: string | null): string {
  if (!value) return "Not set";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function featureLabel(metric: string): string {
  const labels: Record<string, string> = {
    "projects.max": "Projects",
    "reports.monthly": "Reports this month",
    "members.max": "Members",
    "storage.bytes": "Storage",
    ai_generation_units: "AI generation units",
    "search.requests": "Search requests",
  };
  return labels[metric] ?? metric;
}

function displayValue(value: number, unit: string): string {
  return unit === "bytes" ? formatBytes(value) : value.toLocaleString();
}

export function UsageBillingView() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [currentPlan, setCurrentPlan] = useState<WorkspacePlan | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const [busySubscription, setBusySubscription] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedWorkspace = useMemo(
    () => workspaces.find((item) => item.id === workspaceId) ?? null,
    [workspaces, workspaceId],
  );

  const loadWorkspaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await listWorkspaces();
      setWorkspaces(rows);
      setWorkspaceId((current) => current || rows[0]?.id || "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load workspaces.");
    } finally {
      setLoading(false);
    }
  }

  const loadDetails = useCallback(async (id: string) => {
    setLoadingDetails(true);
    setError(null);
    try {
      const [planRows, usageRow, planRow, subscriptionRow] = await Promise.all([
        readJson<Plan[]>("/api/v1/billing/plans"),
        readJson<UsageResponse>("/api/v1/workspaces/" + id + "/usage"),
        readJson<WorkspacePlan>("/api/v1/workspaces/" + id + "/plan"),
        readJson<{ subscription: Record<string, unknown> }>(
          "/api/v1/billing/workspaces/" + id + "/subscription",
        ),
      ]);
      setPlans(planRows);
      setUsage(usageRow);
      setCurrentPlan(planRow);
      const raw = subscriptionRow.subscription;
      setSubscription(raw && Object.keys(raw).length > 0 ? (raw as unknown as Subscription) : null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to load usage and billing data.",
      );
      setUsage(null);
      setCurrentPlan(null);
      setSubscription(null);
    } finally {
      setLoadingDetails(false);
    }
  }

  useEffect(() => { void loadWorkspaces(); }, [loadWorkspaces]);
  useEffect(() => { if (workspaceId) void loadDetails(workspaceId); }, [workspaceId, loadDetails]);

  async function changePlan(plan: Plan) {
    if (!workspaceId) return;
    setBusyPlan(plan.id);
    setError(null);
    try {
      await readJson("/api/v1/billing/workspaces/" + workspaceId + "/plan", {
        method: "POST",
        body: JSON.stringify({ plan_code: plan.code }),
      });
      await loadDetails(workspaceId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to change plan.");
    } finally {
      setBusyPlan(null);
    }
  }

  async function checkout(plan: Plan) {
    if (!workspaceId) return;
    setBusyPlan(plan.id);
    setError(null);
    try {
      const result = await readJson<{ session_id: string; checkout_url: string | null }>(
        "/api/v1/billing/workspaces/" + workspaceId + "/checkout",
        { method: "POST", body: JSON.stringify({ plan_code: plan.code }) },
      );
      if (result.checkout_url) {
        window.location.assign(result.checkout_url);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Checkout is unavailable for this workspace.",
      );
    } finally {
      setBusyPlan(null);
    }
  }

  async function subscriptionAction(action: "cancel" | "resume") {
    if (!workspaceId) return;
    setBusySubscription(true);
    setError(null);
    try {
      await readJson(
        "/api/v1/billing/workspaces/" + workspaceId + "/" + action,
        { method: "POST", body: JSON.stringify({}) },
      );
      await loadDetails(workspaceId);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to update the subscription.",
      );
    } finally {
      setBusySubscription(false);
    }
  }

  const isOwner = selectedWorkspace?.role === "owner";

  if (loading) {
    return (
      <section className="card pad" aria-busy="true">
        <h2>Loading billing workspace…</h2>
        <p className="muted">Reading workspaces and current billing data.</p>
      </section>
    );
  }

  if (workspaces.length === 0) {
    return (
      <section className="card pad">
        <h2>No workspace available</h2>
        <p className="muted">Create a workspace before viewing usage and billing.</p>
      </section>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Workspace plan</div>
          <h1>Usage & billing</h1>
          <p>Live workspace usage, plan entitlements and subscription state.</p>
        </div>
        <div className="actions">
          <label className="field" style={{ minWidth: 240 }}>
            <span className="small muted">Workspace</span>
            <select
              className="input"
              aria-label="Workspace"
              value={workspaceId}
              onChange={(event) => setWorkspaceId(event.target.value)}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {error && (
        <section className="card pad" role="alert" style={{ marginBottom: 16 }}>
          <div className="row">
            <div>
              <h3>Billing request failed</h3>
              <p className="muted small">{error}</p>
            </div>
            <button
              className="btn"
              type="button"
              onClick={() => workspaceId && void loadDetails(workspaceId)}
            >
              Retry
            </button>
          </div>
        </section>
      )}

      <div className="grid grid-2">
        <section className="card pad">
          <div className="row">
            <div>
              <h3>Current subscription</h3>
              <div className="muted small">Source: {subscription?.provider ?? "local workspace state"}</div>
            </div>
            <span className="tag">{subscription?.status ?? "No active subscription"}</span>
          </div>
          <div style={{ marginTop: 16 }}>
            <div className="eyebrow">Plan</div>
            <div style={{ fontSize: 32, fontWeight: 800, marginTop: 4 }}>
              {currentPlan?.name ?? subscription?.plan_code ?? "Unknown"}
            </div>
            <p className="muted small">
              {currentPlan?.description ?? "No plan description is available."}
            </p>
          </div>
          <div className="grid grid-2" style={{ marginTop: 16 }}>
            <div>
              <div className="small muted">Current period</div>
              <b>
                {formatDate(subscription?.current_period_start ?? usage?.period_start ?? null)}
                {" → "}
                {formatDate(subscription?.current_period_end ?? usage?.period_end ?? null)}
              </b>
            </div>
            <div>
              <div className="small muted">Cancellation</div>
              <b>{subscription?.cancel_at_period_end ? "At period end" : "Not scheduled"}</b>
            </div>
          </div>
          {isOwner && subscription && (
            <div className="actions" style={{ marginTop: 18 }}>
              {subscription.cancel_at_period_end ? (
                <button className="btn primary" type="button" disabled={busySubscription} onClick={() => void subscriptionAction("resume")}>
                  {busySubscription ? "Saving…" : "Resume subscription"}
                </button>
              ) : (
                <button className="btn" type="button" disabled={busySubscription} onClick={() => void subscriptionAction("cancel")}>
                  {busySubscription ? "Saving…" : "Cancel at period end"}
                </button>
              )}
            </div>
          )}
        </section>

        <section className="card pad">
          <div className="row">
            <div>
              <h3>Usage this period</h3>
              <div className="muted small">
                {usage ? formatDate(usage.period_start) + " → " + formatDate(usage.period_end) : "Usage data unavailable"}
              </div>
            </div>
            {loadingDetails && <span className="tag">Refreshing…</span>}
          </div>
          <div className="stack" style={{ marginTop: 16 }}>
            {(usage?.items ?? []).map((item) => {
              const percent = item.limit && item.limit > 0
                ? Math.min(100, (item.current / item.limit) * 100)
                : null;
              return (
                <div key={item.metric}>
                  <div className="row small">
                    <span>{featureLabel(item.metric)}</span>
                    <span>
                      <b>{displayValue(item.current, item.unit)}</b>
                      {item.limit !== null ? " / " + displayValue(item.limit, item.unit) : " / unlimited"}
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
              <p className="muted small">No usage metrics are available for this workspace.</p>
            )}
          </div>
        </section>
      </div>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row">
          <div>
            <h3>Available plans</h3>
            <div className="muted small">Plans come from the active billing catalog.</div>
          </div>
          {!isOwner && <span className="tag">Owner access required to change plan</span>}
        </div>
        <div className="grid grid-3" style={{ marginTop: 16 }}>
          {plans.map((plan) => {
            const isCurrent = plan.code === currentPlan?.code;
            return (
              <article className="card pad" key={plan.id}>
                <div className="row">
                  <div>
                    <div className="eyebrow">{plan.code}</div>
                    <h3 style={{ marginTop: 4 }}>{plan.name}</h3>
                  </div>
                  {isCurrent && <span className="tag success">Current</span>}
                </div>
                <p className="muted small" style={{ minHeight: 42 }}>
                  {plan.description ?? "No description provided."}
                </p>
                {isCurrent ? (
                  <button className="btn" type="button" disabled>Current plan</button>
                ) : (
                  <div className="actions">
                    <button
                      className="btn primary"
                      type="button"
                      disabled={!isOwner || busyPlan !== null}
                      onClick={() => void changePlan(plan)}
                    >
                      {busyPlan === plan.id ? "Switching…" : "Switch plan"}
                    </button>
                    <button
                      className="btn"
                      type="button"
                      disabled={!isOwner || busyPlan !== null}
                      onClick={() => void checkout(plan)}
                    >
                      Checkout
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="card pad" style={{ marginTop: 16 }}>
        <h3>Billing records</h3>
        <p className="muted small">
          Invoice history and downloadable invoice files are not exposed by the current backend contract,
          so no synthetic invoice rows are shown here.
        </p>
      </section>
    </>
  );
}
