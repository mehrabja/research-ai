import { apiErrorFromResponse } from "@/lib/api/errors";

export type Plan = {
  id: string;
  code: string;
  name: string;
  description: string | null;
};

export type Entitlement = {
  feature: string;
  limit_value: number | null;
  unit: string;
};

export type WorkspacePlan = Plan & {
  entitlements: Entitlement[];
};

export type UsageItem = {
  metric: string;
  current: number;
  limit: number | null;
  unit: string;
};

export type UsageResponse = {
  workspace_id: string;
  period_start: string;
  period_end: string;
  items: UsageItem[];
};

export type Subscription = {
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

  if (!response.ok) {
    throw await apiErrorFromResponse(response, "Billing request failed.");
  }

  return (await response.json()) as T;
}

export async function listBillingPlans(): Promise<Plan[]> {
  return readJson<Plan[]>("/api/v1/billing/plans");
}

export async function getWorkspaceUsage(
  workspaceId: string,
): Promise<UsageResponse> {
  return readJson<UsageResponse>(
    "/api/v1/workspaces/" + workspaceId + "/usage",
  );
}

export async function getWorkspacePlan(
  workspaceId: string,
): Promise<WorkspacePlan> {
  return readJson<WorkspacePlan>(
    "/api/v1/workspaces/" + workspaceId + "/plan",
  );
}

export async function getWorkspaceSubscription(
  workspaceId: string,
): Promise<Subscription | null> {
  const result = await readJson<{ subscription: Record<string, unknown> }>(
    "/api/v1/billing/workspaces/" + workspaceId + "/subscription",
  );
  const raw = result.subscription;
  return Object.keys(raw).length > 0 ? (raw as unknown as Subscription) : null;
}

export async function switchWorkspacePlan(
  workspaceId: string,
  planCode: string,
): Promise<unknown> {
  return readJson(
    "/api/v1/billing/workspaces/" + workspaceId + "/plan",
    { method: "POST", body: JSON.stringify({ plan_code: planCode }) },
  );
}

export async function createWorkspaceCheckout(
  workspaceId: string,
  planCode: string,
): Promise<{ session_id: string; checkout_url: string | null }> {
  return readJson(
    "/api/v1/billing/workspaces/" + workspaceId + "/checkout",
    { method: "POST", body: JSON.stringify({ plan_code: planCode }) },
  );
}

export async function changeSubscription(
  workspaceId: string,
  action: "cancel" | "resume",
): Promise<unknown> {
  return readJson(
    "/api/v1/billing/workspaces/" + workspaceId + "/" + action,
    { method: "POST", body: JSON.stringify({}) },
  );
}
