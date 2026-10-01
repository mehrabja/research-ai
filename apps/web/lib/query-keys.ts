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
  notifications: (limit: number) =>
    ["notifications", limit] as const,
  workspaceUsage: (workspaceId: string) =>
    ["workspace-usage", workspaceId] as const,
} as const;
