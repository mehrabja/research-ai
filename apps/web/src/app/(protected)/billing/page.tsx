"use client";

import { useWorkspace } from "@/components/app-shell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export default function BillingPage() {
  const { workspaceId } = useWorkspace();
  const qc = useQueryClient();
  const plan = useQuery({
    queryKey: ["plan", workspaceId],
    queryFn: () => api.plan(workspaceId!),
    enabled: !!workspaceId,
  });
  const subscription = useQuery({
    queryKey: ["subscription", workspaceId],
    queryFn: () => api.subscription(workspaceId!),
    enabled: !!workspaceId,
  });
  const checkout = useMutation({
    mutationFn: (planCode: string) => api.checkout(workspaceId!, planCode),
    onSuccess: (result) => {
      if (result.checkout_url) window.location.assign(result.checkout_url);
    },
  });
  const cancel = useMutation({
    mutationFn: () => api.cancelSubscription(workspaceId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscription", workspaceId] }),
  });
  const resume = useMutation({
    mutationFn: () => api.resumeSubscription(workspaceId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscription", workspaceId] }),
  });

  if (!workspaceId) return <div className="card p-6 muted">Loading workspace…</div>;

  const sub = subscription.data?.subscription ?? {};
  const provider = typeof sub.provider === "string" ? sub.provider : "—";
  const status = typeof sub.status === "string" ? sub.status : "—";
  const planCode = typeof sub.plan_code === "string" ? sub.plan_code : plan.data?.code;

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">Workspace billing</div>
        <h1 className="text-3xl font-semibold mt-2">Billing</h1>
        <p className="muted mt-2">
          Plan entitlements and subscription state are authoritative on the backend.
        </p>
      </header>

      <section className="card p-6">
        {subscription.isPending || plan.isPending ? (
          <div className="muted">Loading billing state…</div>
        ) : plan.error ? (
          <div style={{ color: "var(--danger)" }}>{plan.error.message}</div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xl font-semibold">{plan.data?.name}</div>
                <div className="muted mt-1">{planCode} · {provider} · {status}</div>
              </div>
              <div className="flex gap-2">
                {status !== "canceled" && !Boolean(sub.cancel_at_period_end) && (
                  <button className="btn btn-secondary" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
                    {cancel.isPending ? "Canceling…" : "Cancel at period end"}
                  </button>
                )}
                {Boolean(sub.cancel_at_period_end) && (
                  <button className="btn btn-primary" disabled={resume.isPending} onClick={() => resume.mutate()}>
                    {resume.isPending ? "Resuming…" : "Resume"}
                  </button>
                )}
              </div>
            </div>

            <div className="mt-5 grid md:grid-cols-2 gap-3">
              {(plan.data?.entitlements ?? []).map((e) => (
                <div key={e.feature} className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
                  <div>{e.feature}</div>
                  <div className="muted text-sm mt-1">
                    {e.limit_value == null ? "Unlimited" : String(e.limit_value) + " " + e.unit}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {["free", "pro", "team"].map((code) => (
                <button
                  key={code}
                  className={code === plan.data?.code ? "btn btn-secondary" : "btn btn-primary"}
                  disabled={code === plan.data?.code || checkout.isPending}
                  onClick={() => checkout.mutate(code)}
                >
                  {checkout.isPending && checkout.variables === code
                    ? "Opening checkout…"
                    : code === plan.data?.code
                      ? "Current: " + code
                      : "Choose " + code}
                </button>
              ))}
            </div>

            {checkout.error && <div className="text-sm mt-3" style={{ color: "var(--danger)" }}>{checkout.error.message}</div>}
            {cancel.error && <div className="text-sm mt-3" style={{ color: "var(--danger)" }}>{cancel.error.message}</div>}
            {resume.error && <div className="text-sm mt-3" style={{ color: "var(--danger)" }}>{resume.error.message}</div>}
          </>
        )}
      </section>
    </div>
  );
}
