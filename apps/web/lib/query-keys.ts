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
  sources: (reportId: string | null) =>
    ["sources", reportId] as const,
  projectFolders: (projectId: string | null) =>
    ["project-folders", projectId] as const,
  projectFiles: (
    projectId: string | null,
    folderId: string | null = null,
  ) => ["project-files", projectId, folderId] as const,
  projectFileEvidence: (projectId: string | null) =>
    ["project-file-evidence", projectId] as const,
  fileMeta: (fileId: string | null) => ["file-meta", fileId] as const,
  fileCodeAnalysis: (fileId: string | null) =>
    ["file-code-analysis", fileId] as const,
  fileCodeSymbols: (fileId: string | null) =>
    ["file-code-symbols", fileId] as const,
  fileCodeDependencies: (fileId: string | null) =>
    ["file-code-dependencies", fileId] as const,
  fileDataProfile: (fileId: string | null) =>
    ["file-data-profile", fileId] as const,
  fileDataColumns: (fileId: string | null) =>
    ["file-data-columns", fileId] as const,
} as const;
