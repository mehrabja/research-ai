import type { components } from "./generated";

type Schema = components["schemas"];

export type User = Schema["UserResponse"];

export type Workspace = Schema["WorkspaceListItem"];
export type WorkspaceDetail = Schema["WorkspaceRead"];

export type Project = Schema["ProjectRead"];
export type ProjectList = Schema["ProjectListResponse"];

export type Report = Schema["ReportResponse"];

export type SourceCandidate = Schema["SourceCandidateRead"];
export type Source = Schema["SourceRead"];

export type RAGResponse = Schema["RetrieveResponse"];

export type Member = Schema["MemberRead"];
export type Invitation = Schema["InvitationRead"];

export type Usage = Schema["UsageResponse"];
export type Plan = Schema["PlanRead"];

export type Manuscript = Schema["ManuscriptCurrentRead"];
export type Citation = Schema["CitationCurrentRead"];
export type QA = Schema["AcademicQACurrentRead"];

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string | null;
  details: unknown;

  constructor(
    message: string,
    status: number,
    code = "API_ERROR",
    requestId: string | null = null,
    details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(
    "/api/backend/" + path.replace(/^\//, ""),
    {
      ...init,
      headers: {
        ...(init?.body
          ? { "content-type": "application/json" }
          : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    },
  );

  const body = await res.json().catch(() => null);

  if (!res.ok) {
    const error = body?.error ?? body;

    const message =
      error?.message ??
      body?.detail ??
      body?.message ??
      `Request failed (${res.status})`;

    throw new ApiError(
      typeof message === "string"
        ? message
        : JSON.stringify(message),
      res.status,
      typeof error?.code === "string"
        ? error.code
        : "API_ERROR",
      typeof error?.request_id === "string"
        ? error.request_id
        : res.headers.get("x-request-id"),
      error?.details ?? error?.extra,
    );
  }

  return body as T;
}

export const api = {
  me: () =>
    request<User>("auth/me"),

  sessions: () =>
    request<
      Array<{
        id: string;
        created_at: string;
        expires_at: string;
        last_used_at: string | null;
      }>
    >("auth/sessions"),

  revokeSession: (id: string) =>
    request<object>(
      "auth/sessions/" + id,
      { method: "DELETE" },
    ),

  workspaces: () =>
    request<{
      items: Workspace[];
      total: number;
    }>("workspaces"),

  createWorkspace: (name: string) =>
    request<WorkspaceDetail>(
      "workspaces",
      {
        method: "POST",
        body: JSON.stringify({ name }),
      },
    ),

  projects: (workspaceId: string) =>
    request<ProjectList>(
      "projects?workspace_id=" +
        encodeURIComponent(workspaceId),
    ),

  project: (
    projectId: string,
    workspaceId: string,
  ) =>
    request<Project>(
      "projects/" +
        projectId +
        "?workspace_id=" +
        encodeURIComponent(workspaceId),
    ),

  createProject: (
    workspaceId: string,
    body: object,
  ) =>
    request<Project>(
      "projects?workspace_id=" +
        encodeURIComponent(workspaceId),
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  projectReports: (
    projectId: string,
    workspaceId: string,
  ) =>
    request<{
      items: Array<{
        id: string;
        topic: string;
        status: string;
        output_language: string;
        updated_at: string;
      }>;
      total: number;
      limit?: number;
      offset?: number;
    }>(
      "projects/" +
        projectId +
        "/reports?workspace_id=" +
        encodeURIComponent(workspaceId),
    ),

  reports: (workspaceId: string) =>
    request<Report[]>(
      "reports?workspace_id=" +
        encodeURIComponent(workspaceId),
    ),

  createReport: (
    workspaceId: string,
    body: object,
  ) =>
    request<Report>(
      "reports?workspace_id=" +
        encodeURIComponent(workspaceId),
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  report: (reportId: string) =>
    request<Report>(
      "reports/" + reportId,
    ),

  sources: (reportId: string) =>
    request<{
      items: Source[];
    }>(
      "reports/" + reportId + "/sources",
    ),

  searchSources: (
    reportId: string,
    query: string,
  ) =>
    request<{
      query: string;
      limit: number;
      candidates: SourceCandidate[];
    }>(
      "reports/" +
        reportId +
        "/sources/search?q=" +
        encodeURIComponent(query) +
        "&limit=8",
    ),

  createSource: (
    reportId: string,
    candidate: SourceCandidate,
  ) =>
    request<Source>(
      "reports/" + reportId + "/sources",
      {
        method: "POST",
        body: JSON.stringify(candidate),
      },
    ),

  ragRetrieve: (
    projectId: string,
    body: object,
  ) =>
    request<RAGResponse>(
      "projects/" +
        projectId +
        "/rag/retrieve",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  manuscript: (reportId: string) =>
    request<Manuscript>(
      "reports/" +
        reportId +
        "/manuscript",
    ),

  citations: (reportId: string) =>
    request<Citation>(
      "reports/" +
        reportId +
        "/citations/current",
    ),

  qa: (reportId: string) =>
    request<QA>(
      "reports/" +
        reportId +
        "/academic-qa/current",
    ),

  members: (workspaceId: string) =>
    request<{
      items: Member[];
      total: number;
    }>(
      "workspaces/" +
        workspaceId +
        "/members",
    ),

  changeMemberRole: (
    workspaceId: string,
    userId: string,
    role: string,
  ) =>
    request<Member>(
      "workspaces/" +
        workspaceId +
        "/members/" +
        userId,
      {
        method: "PATCH",
        body: JSON.stringify({ role }),
      },
    ),

  removeMember: (
    workspaceId: string,
    userId: string,
  ) =>
    request<null>(
      "workspaces/" +
        workspaceId +
        "/members/" +
        userId,
      {
        method: "DELETE",
      },
    ),

  invitations: (workspaceId: string) =>
    request<{
      items: Invitation[];
      total: number;
    }>(
      "workspaces/" +
        workspaceId +
        "/members/invitations",
    ),

  invite: (
    workspaceId: string,
    body: object,
  ) =>
    request<{
      invitation: Invitation;
      token: string;
    }>(
      "workspaces/" +
        workspaceId +
        "/members/invitations",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  revokeInvitation: (
    workspaceId: string,
    invitationId: string,
  ) =>
    request<null>(
      "workspaces/" +
        workspaceId +
        "/members/invitations/" +
        invitationId,
      {
        method: "DELETE",
      },
    ),

  transferOwnership: (
    workspaceId: string,
    userId: string,
  ) =>
    request<WorkspaceDetail>(
      "workspaces/" +
        workspaceId +
        "/transfer-ownership",
      {
        method: "POST",
        body: JSON.stringify({
          target_user_id: userId,
        }),
      },
    ),

  usage: (workspaceId: string) =>
    request<Usage>(
      "workspaces/" +
        workspaceId +
        "/usage",
    ),

  plans: () =>
    request<
      Array<{
        id: string;
        code: string;
        name: string;
        description: string | null;
      }>
    >("billing/plans"),

  plan: (workspaceId: string) =>
    request<Plan>(
      "workspaces/" +
        workspaceId +
        "/plan",
    ),

  subscription: (workspaceId: string) =>
    request<{
      subscription: Record<string, unknown>;
    }>(
      "billing/workspaces/" +
        workspaceId +
        "/subscription",
    ),

  checkout: (
    workspaceId: string,
    planCode: string,
  ) =>
    request<{
      session_id: string;
      checkout_url: string | null;
    }>(
      "billing/workspaces/" +
        workspaceId +
        "/checkout",
      {
        method: "POST",
        body: JSON.stringify({
          plan_code: planCode,
        }),
      },
    ),

  changePlan: (
    workspaceId: string,
    planCode: string,
  ) =>
    request<{
      status: string;
      subscription_id: string;
      cancel_at_period_end: boolean;
    }>(
      "workspaces/" +
        workspaceId +
        "/plan",
      {
        method: "POST",
        body: JSON.stringify({
          plan_code: planCode,
        }),
      },
    ),

  cancelSubscription: (workspaceId: string) =>
    request<object>(
      "billing/workspaces/" +
        workspaceId +
        "/cancel",
      {
        method: "POST",
      },
    ),

  resumeSubscription: (workspaceId: string) =>
    request<object>(
      "billing/workspaces/" +
        workspaceId +
        "/resume",
      {
        method: "POST",
      },
    ),

  notifications: (workspaceId: string) =>
    request<{
      items: Array<{
        id: string;
        kind: string;
        title: string;
        body: string;
        read_at: string | null;
        created_at: string;
      }>;
      total: number;
      unread: number;
    }>(
      "notifications?workspace_id=" +
        encodeURIComponent(workspaceId),
    ),

  readNotification: (notificationId: string) =>
    request<object>(
      "notifications/" +
        notificationId +
        "/read",
      {
        method: "POST",
      },
    ),

  readAllNotifications: (
    workspaceId: string,
  ) =>
    request<null>(
      "notifications/read-all?workspace_id=" +
        encodeURIComponent(workspaceId),
      {
        method: "POST",
      },
    ),

  notificationPreferences: () =>
    request<{
      preferences: Record<string, boolean>;
    }>(
      "notifications/preferences",
    ),

  updateNotificationPreferences: (
    preferences: Record<string, boolean>,
  ) =>
    request<{
      preferences: Record<string, boolean>;
    }>(
      "notifications/preferences",
      {
        method: "PATCH",
        body: JSON.stringify({ preferences }),
      },
    ),

  createAPIToken: (
    body: {
      name: string;
      expires_at?: string | null;
    },
  ) =>
    request<{
      id: string;
      name: string;
      token: string;
      token_prefix: string;
      expires_at: string | null;
    }>(
      "auth/api-tokens",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  apiTokens: () =>
    request<
      Array<{
        id: string;
        name: string;
        token_prefix: string;
        last_used_at: string | null;
        expires_at: string | null;
        revoked_at: string | null;
        created_at: string;
      }>
    >(
      "auth/api-tokens",
    ),

  revokeAPIToken: (tokenId: string) =>
    request<null>(
      "auth/api-tokens/" +
        tokenId,
      {
        method: "DELETE",
      },
    ),

  mfaStatus: () =>
    request<{
      enabled: boolean;
      recovery_codes_remaining: number;
    }>(
      "auth/mfa",
    ),

  mfaSetup: () =>
    request<{
      secret: string;
      provisioning_uri: string;
      recovery_codes: string[];
    }>(
      "auth/mfa/setup",
      {
        method: "POST",
      },
    ),

  mfaEnable: (code: string) =>
    request<{
      enabled: boolean;
      recovery_codes_remaining: number;
    }>(
      "auth/mfa/enable",
      {
        method: "POST",
        body: JSON.stringify({ code }),
      },
    ),

  mfaDisable: (code: string) =>
    request<{
      enabled: boolean;
      recovery_codes_remaining: number;
    }>(
      "auth/mfa/disable",
      {
        method: "POST",
        body: JSON.stringify({ code }),
      },
    ),

  search: (
    workspaceId: string,
    query: string,
  ) =>
    request<{
      query: string;
      items: Array<{
        id: string;
        resource_type: string;
        title: string;
        snippet: string | null;
        updated_at: string;
      }>;
      total: number;
    }>(
      "search?workspace_id=" +
        encodeURIComponent(workspaceId) +
        "&q=" +
        encodeURIComponent(query),
    ),

  evidenceMatrix: (reportId: string) =>
    request<object>(
      "reports/" +
        reportId +
        "/evidence/matrix",
    ),

  graphExport: (projectId: string) =>
    request<object>(
      "projects/" +
        projectId +
        "/knowledge-graph/export",
    ),

  savePlanRevision: (
    projectId: string,
    body: object,
  ) =>
    request<object>(
      "projects/" +
        projectId +
        "/research-plan",
      {
        method: "PATCH",
        body: JSON.stringify(body),
      },
    ),

  restorePlanVersion: (
    projectId: string,
    version: number,
  ) =>
    request<object>(
      "projects/" +
        projectId +
        "/research-plan/restore",
      {
        method: "POST",
        body: JSON.stringify({
          target_version: version,
        }),
      },
    ),

  manuscriptDraft: (reportId: string) =>
    request<object>(
      "reports/" +
        reportId +
        "/manuscript/draft",
    ),

  saveManuscriptDraft: (
    reportId: string,
    body: object,
  ) =>
    request<object>(
      "reports/" +
        reportId +
        "/manuscript/draft",
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),

  commitManuscriptDraft: (
    reportId: string,
    body: object,
  ) =>
    request<object>(
      "reports/" +
        reportId +
        "/manuscript/draft/commit",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  providerMatrix: () =>
    request<{
      capabilities: Array<{
        capability: string;
        configured_preferred: string;
        available_providers: string[];
      }>;
    }>(
      "providers/matrix",
    ),

  folders: (projectId: string) =>
    request<{
      items: Array<{
        id: string;
        project_id: string;
        parent_id: string | null;
        name: string;
        created_at: string;
        updated_at: string;
      }>;
      total: number;
    }>(
      "projects/" +
        projectId +
        "/folders",
    ),

  createFolder: (
    projectId: string,
    body: {
      name: string;
      parent_id?: string | null;
    },
  ) =>
    request<object>(
      "projects/" +
        projectId +
        "/folders",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  moveFile: (
    fileId: string,
    folderId: string | null,
  ) =>
    request<object>(
      "files/" +
        fileId +
        "/move" +
        (folderId
          ? "?folder_id=" +
            encodeURIComponent(folderId)
          : ""),
      {
        method: "POST",
      },
    ),

  jobs: () =>
    request<
      Array<{
        id: string;
        job_type: string;
        status: string;
        attempt_count: number;
        max_attempts: number;
        created_at: string;
        last_error_message: string | null;
      }>
    >("jobs"),

  retryJob: (jobId: string) =>
    request<object>(
      "jobs/" +
        jobId +
        "/retry",
      {
        method: "POST",
      },
    ),
};

export type FeaturePagePayload = {
  title: string;
  description: string;
  metrics: Array<{
    label: string;
    value: string | number;
  }>;
  links: Array<{
    label: string;
    href: string;
  }>;
};