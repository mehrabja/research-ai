export const queryKeys = {
  session: ["session", "user"] as const,
  workspaces: ["workspaces"] as const,
  projects: (workspaceId: string | null) =>
    ["projects", workspaceId] as const,
  projectReports: (projectId: string | null) =>
    ["project-reports", projectId] as const,
  teamMembers: (workspaceId: string | null) =>
    ["team-members", workspaceId] as const,
  invitations: (workspaceId: string | null) =>
    ["workspace-invitations", workspaceId] as const,
  notifications: (limit: number, workspaceId: string | null = null) =>
    ["notifications", workspaceId, limit] as const,
  workspaceUsage: (workspaceId: string) =>
    ["workspace-usage", workspaceId] as const,
  billingPlans: ["billing-plans"] as const,
  workspacePlan: (workspaceId: string) =>
    ["workspace-plan", workspaceId] as const,
  workspaceSubscription: (workspaceId: string) =>
    ["workspace-subscription", workspaceId] as const,
} as const;
