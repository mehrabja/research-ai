import type { components } from "./generated";

type Schema = components["schemas"];

export type User = Schema["UserResponse"];

export type Workspace = Schema["WorkspaceListItem"];
export type WorkspaceDetail = Schema["WorkspaceRead"];

export type Project = Schema["ProjectRead"];
export type ProjectList = Schema["ProjectListResponse"];
export type ProjectUpdate = Schema["ProjectUpdate"];

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

export type LiteratureItem = Schema["LiteratureItemRead"];
export type LiteratureCluster = Schema["LiteratureClusterRead"];
export type LiteratureGap = Schema["LiteratureGapRead"];
export type LiteratureRun = Schema["LiteratureRunRead"];
export type ResearchPlan = Schema["ResearchPlanRead"];

export type KnowledgeGraph = Schema["KnowledgeGraphRead"];
export type KnowledgeGraphSummary = Schema["KnowledgeGraphSummaryRead"];
export type KnowledgeGraphNeighbor = Schema["KnowledgeGraphNeighborRead"];

export type EvidenceMatrix = Schema["EvidenceMatrixRead"];

export type ProjectFile = Schema["ProjectFileRead"];
export type ProjectFileList = Schema["ProjectFileListResponse"];

export type PreTranslationReview =
  Schema["PreTranslationReviewResponse"];

export type ProjectMember = Schema["ProjectMemberRead"];
export type ManuscriptComment = Schema["ManuscriptCommentRead"];
export type ManuscriptReviewTask =
  Schema["ManuscriptReviewTaskRead"];

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
  const isFormData =
    typeof FormData !== "undefined" &&
    init?.body instanceof FormData;

  const res = await fetch(
    "/api/backend/" + path.replace(/^\//, ""),
    {
      ...init,
      headers: {
        ...(!isFormData && init?.body
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

  updateProject: (
    projectId: string,
    workspaceId: string,
    body: ProjectUpdate,
  ) =>
    request<Project>(
      "projects/" +
        projectId +
        "?workspace_id=" +
        encodeURIComponent(workspaceId),
      {
        method: "PATCH",
        body: JSON.stringify(body),
      },
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
    options?: {
      limit?: number;
      year?: number;
      open_access?: boolean;
      min_citations?: number;
      max_citations?: number;
      author?: string;
      venue?: string;
      year_from?: number;
      year_to?: number;
      publication_type?: string;
      language?: string;
      sort_by?:
        | "relevance"
        | "year"
        | "citations"
        | "title";
      sort_order?: "asc" | "desc";
    },
  ) => {
    const params = new URLSearchParams({
      q: query,
      limit: String(options?.limit ?? 8),
    });

    if (options?.year !== undefined) {
      params.set("year", String(options.year));
    }

    if (options?.open_access !== undefined) {
      params.set(
        "open_access",
        String(options.open_access),
      );
    }

    if (options?.min_citations !== undefined) {
      params.set(
        "min_citations",
        String(options.min_citations),
      );
    }

    if (options?.max_citations !== undefined) {
      params.set(
        "max_citations",
        String(options.max_citations),
      );
    }

    if (options?.author) {
      params.set("author", options.author);
    }

    if (options?.venue) {
      params.set("venue", options.venue);
    }

    if (options?.year_from !== undefined) {
      params.set(
        "year_from",
        String(options.year_from),
      );
    }

    if (options?.year_to !== undefined) {
      params.set(
        "year_to",
        String(options.year_to),
      );
    }

    if (options?.publication_type) {
      params.set(
        "publication_type",
        options.publication_type,
      );
    }

    if (options?.language) {
      params.set(
        "language",
        options.language,
      );
    }

    if (options?.sort_by) {
      params.set(
        "sort_by",
        options.sort_by,
      );
    }

    if (options?.sort_order) {
      params.set(
        "sort_order",
        options.sort_order,
      );
    }

    return request<{
      query: string;
      limit: number;
      candidates: SourceCandidate[];
    }>(
      "reports/" +
        reportId +
        "/sources/search?" +
        params.toString(),
    );
  },

  createSource: (
    reportId: string,
    candidate: SourceCandidate,
  ) =>
    request<Source>(
      "reports/" +
        reportId +
        "/sources",
      {
        method: "POST",
        body: JSON.stringify(candidate),
      },
    ),

  extractSource: (
    reportId: string,
    sourceId: string,
  ) =>
    request<{
      source_id: string;
      status: string;
      content_hash: string | null;
      chunk_count: number;
      content_type: string | null;
      content_length: number | null;
      extracted_at: string | null;
      pipeline_version: string | null;
    }>(
      "reports/" +
        reportId +
        "/sources/" +
        sourceId +
        "/extract",
      {
        method: "POST",
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
  generateManuscript: (
    reportId: string,
    force = false,
    async = true,
  ) =>
    request<Schema["ManuscriptGenerateResponse"]>(
      "reports/" +
        reportId +
        "/manuscript/generate",
      {
        method: "POST",
        body: JSON.stringify({
          force,
          async,
        }),
      },
    ),

  validateManuscript: (
    reportId: string,
  ) =>
    request<Schema["ManuscriptValidationRead"]>(
      "reports/" +
        reportId +
        "/manuscript/validate",
      {
        method: "POST",
      },
    ),

  manuscriptSection: (
    reportId: string,
    sectionKey: string,
  ) =>
    request<Schema["ManuscriptSectionRead"]>(
      "reports/" +
        reportId +
        "/manuscript/sections/" +
        encodeURIComponent(sectionKey),
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
  enqueueTranslation: (
    reportId: string,
    body: {
      source_version_id: string;
      target_language: string;
    },
  ) =>
    request<{
      job_id: string;
      status: string;
    }>(
      "reports/" +
        reportId +
        "/translation/enqueue",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  evidenceMatrix: (reportId: string) =>
    request<EvidenceMatrix>(
      "reports/" +
        reportId +
        "/evidence/matrix",
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

  readNotification: (
    notificationId: string,
  ) =>
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
    >("auth/api-tokens"),

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
    }>("auth/mfa"),

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

  graphExport: (projectId: string) =>
    request<object>(
      "projects/" +
        projectId +
        "/knowledge-graph/export",
    ),

  knowledgeGraph: (projectId: string) =>
    request<KnowledgeGraph>(
      "projects/" +
        projectId +
        "/knowledge-graph",
    ),

  knowledgeGraphSummary: (
    projectId: string,
  ) =>
    request<KnowledgeGraphSummary>(
      "projects/" +
        projectId +
        "/knowledge-graph/summary",
    ),

  generateKnowledgeGraph: (
    projectId: string,
    force = false,
    async = true,
  ) =>
    request<{
      status: string;
      job_id: string | null;
      graph: KnowledgeGraph | null;
    }>(
      "projects/" +
        projectId +
        "/knowledge-graph/generate",
      {
        method: "POST",
        body: JSON.stringify({
          force,
          async,
        }),
      },
    ),

  queryKnowledgeGraph: (
    projectId: string,
    body: {
      start_node_id: string;
      max_depth?: number;
      max_nodes?: number;
      relation_types?: string[];
    },
  ) =>
    request<{
      graph_version_id: string;
      start_node_id: string;
      max_depth: number;
      max_nodes: number;
      nodes: Array<Record<string, unknown>>;
      edges: Array<Record<string, unknown>>;
    }>(
      "projects/" +
        projectId +
        "/knowledge-graph/query",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  literature: (
    projectId: string,
    options?: {
      screening_status?: string;
      relevance_min?: number;
      paper_type?: string;
      research_design?: string;
      analysis_status?: string;
      limit?: number;
      offset?: number;
    },
  ) => {
    const params = new URLSearchParams();

    if (options?.screening_status) {
      params.set(
        "screening_status",
        options.screening_status,
      );
    }

    if (options?.relevance_min !== undefined) {
      params.set(
        "relevance_min",
        String(options.relevance_min),
      );
    }

    if (options?.paper_type) {
      params.set(
        "paper_type",
        options.paper_type,
      );
    }

    if (options?.research_design) {
      params.set(
        "research_design",
        options.research_design,
      );
    }

    if (options?.analysis_status) {
      params.set(
        "analysis_status",
        options.analysis_status,
      );
    }

    params.set(
      "limit",
      String(options?.limit ?? 50),
    );

    params.set(
      "offset",
      String(options?.offset ?? 0),
    );

    return request<{
      items: LiteratureItem[];
      total: number;
      limit: number;
      offset: number;
    }>(
      "projects/" +
        projectId +
        "/literature?" +
        params.toString(),
    );
  },

  analyzeLiterature: (
    projectId: string,
    force = false,
  ) =>
    request<{
      status: string;
      job_id: string | null;
      run: LiteratureRun | null;
    }>(
      "projects/" +
        projectId +
        "/literature/analyze",
      {
        method: "POST",
        body: JSON.stringify({ force }),
      },
    ),

  updateLiteratureScreening: (
    projectId: string,
    itemId: string,
    screeningStatus:
      | "discovered"
      | "candidate"
      | "included"
      | "excluded"
      | "uncertain",
    reason?: string,
  ) =>
    request<LiteratureItem>(
      "projects/" +
        projectId +
        "/literature/" +
        itemId,
      {
        method: "PATCH",
        body: JSON.stringify({
          screening_status:
            screeningStatus,
          ...(reason ? { reason } : {}),
        }),
      },
    ),

  literatureClusters: (
    projectId: string,
  ) =>
    request<{
      items: LiteratureCluster[];
      total: number;
    }>(
      "projects/" +
        projectId +
        "/literature/clusters",
    ),

  literatureGaps: (
    projectId: string,
  ) =>
    request<{
      items: LiteratureGap[];
      total: number;
    }>(
      "projects/" +
        projectId +
        "/literature/gaps",
    ),

  literatureRuns: (
    projectId: string,
    limit = 50,
    offset = 0,
  ) =>
    request<{
      items: LiteratureRun[];
      total: number;
      limit: number;
      offset: number;
    }>(
      "projects/" +
        projectId +
        "/literature/runs?limit=" +
        encodeURIComponent(String(limit)) +
        "&offset=" +
        encodeURIComponent(String(offset)),
    ),

  researchPlan: (
    projectId: string,
  ) =>
    request<ResearchPlan>(
      "projects/" +
        projectId +
        "/research-plan",
    ),

  generateResearchPlan: (
    projectId: string,
    force = false,
    async = true,
  ) =>
    request<{
      status: string;
      job_id: string | null;
      plan: ResearchPlan | null;
    }>(
      "projects/" +
        projectId +
        "/research-plan/generate",
      {
        method: "POST",
        body: JSON.stringify({
          force,
          async,
        }),
      },
    ),

  researchPlanCoverage: (
    projectId: string,
  ) =>
    request<{
      coverage_score: number;
      coverage_state: string;
      per_requirement: Array<
        Record<string, unknown>
      >;
    }>(
      "projects/" +
        projectId +
        "/research-plan/coverage",
    ),

  validateResearchPlan: (
    projectId: string,
  ) =>
    request<{
      validation_status: string;
      validation_errors: string[];
      completeness_score: number | null;
    }>(
      "projects/" +
        projectId +
        "/research-plan/validate",
    ),

  saveResearchPlan: (
    projectId: string,
    body: {
      research_objective_snapshot?:
        | string
        | null;
      research_questions_snapshot?:
        | unknown[]
        | null;
      hypotheses_snapshot?:
        | unknown[]
        | null;
      budget?:
        | Record<string, unknown>
        | null;
      planning_mode?: string | null;
    },
  ) =>
    request<ResearchPlan>(
      "projects/" +
        projectId +
        "/research-plan",
      {
        method: "PATCH",
        body: JSON.stringify(body),
      },
    ),

  restoreResearchPlan: (
    projectId: string,
    targetVersion: number,
  ) =>
    request<ResearchPlan>(
      "projects/" +
        projectId +
        "/research-plan/restore",
      {
        method: "POST",
        body: JSON.stringify({
          target_version:
            targetVersion,
        }),
      },
    ),

  files: (
    projectId: string,
    options?: {
      status?: string;
      kind?: string;
      folder_id?: string;
      limit?: number;
      offset?: number;
    },
  ) => {
    const params = new URLSearchParams();

    if (options?.status) {
      params.set("status", options.status);
    }

    if (options?.kind) {
      params.set("kind", options.kind);
    }

    if (options?.folder_id) {
      params.set(
        "folder_id",
        options.folder_id,
      );
    }

    params.set(
      "limit",
      String(options?.limit ?? 50),
    );

    params.set(
      "offset",
      String(options?.offset ?? 0),
    );

    return request<ProjectFileList>(
      "projects/" +
        projectId +
        "/files?" +
        params.toString(),
    );
  },

  uploadFile: (
    projectId: string,
    file: File,
    folderId?: string | null,
  ) => {
    const form = new FormData();
    form.append("file", file);

    let path =
      "projects/" +
      projectId +
      "/files";

    if (folderId) {
      path +=
        "?folder_id=" +
        encodeURIComponent(folderId);
    }

    return request<ProjectFile>(
      path,
      {
        method: "POST",
        body: form,
      },
    );
  },

  file: (fileId: string) =>
    request<ProjectFile>(
      "files/" + fileId,
    ),

  deleteFile: (fileId: string) =>
    request<null>(
      "files/" + fileId,
      {
        method: "DELETE",
      },
    ),

  moveFile: (
    fileId: string,
    folderId: string | null,
  ) =>
    request<ProjectFile>(
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

  downloadFile: async (
    fileId: string,
  ): Promise<Blob> => {
    const res = await fetch(
      "/api/backend/files/" +
        encodeURIComponent(fileId) +
        "/content",
      {
        cache: "no-store",
      },
    );

    if (!res.ok) {
      const body = await res.json().catch(() => null);
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
        error?.details ??
          error?.extra,
      );
    }

    return res.blob();
  },

  preTranslationReview: (
    reportId: string,
  ) =>
    request<PreTranslationReview>(
      "reports/" +
        reportId +
        "/review/pre-translation",
    ),

  editPreTranslationReview: (
    reportId: string,
    body: {
      version_id: string;
      content: string;
      notes?: string | null;
    },
  ) =>
    request<PreTranslationReview>(
      "reports/" +
        reportId +
        "/review/pre-translation/edit",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  approvePreTranslationReview: (
    reportId: string,
    versionId: string,
  ) =>
    request<PreTranslationReview>(
      "reports/" +
        reportId +
        "/review/pre-translation/approve",
      {
        method: "POST",
        body: JSON.stringify({
          version_id: versionId,
        }),
      },
    ),

  requestPreTranslationChanges: (
    reportId: string,
    versionId: string,
    notes: string,
  ) =>
    request<PreTranslationReview>(
      "reports/" +
        reportId +
        "/review/pre-translation/request-changes",
      {
        method: "POST",
        body: JSON.stringify({
          version_id: versionId,
          notes,
        }),
      },
    ),

  rejectPreTranslationReview: (
    reportId: string,
    versionId: string,
    notes: string,
  ) =>
    request<PreTranslationReview>(
      "reports/" +
        reportId +
        "/review/pre-translation/reject",
      {
        method: "POST",
        body: JSON.stringify({
          version_id: versionId,
          notes,
        }),
      },
    ),

  projectMembers: (
    projectId: string,
  ) =>
    request<{
      items: ProjectMember[];
      total: number;
      limit: number;
      offset: number;
    }>(
      "projects/" +
        projectId +
        "/members",
    ),

  reviewTasks: (
    reportId: string,
    versionId: string,
  ) =>
    request<{
      items: ManuscriptReviewTask[];
      total: number;
      limit: number;
      offset: number;
    }>(
      "reports/" +
        reportId +
        "/manuscript-versions/" +
        versionId +
        "/reviews",
    ),

  changeReviewTaskStatus: (
    reportId: string,
    reviewTaskId: string,
    status: string,
    resolution?: Record<string, unknown>,
  ) =>
    request<ManuscriptReviewTask>(
      "reports/" +
        reportId +
        "/reviews/" +
        reviewTaskId,
      {
        method: "PATCH",
        body: JSON.stringify({
          status,
          ...(resolution
            ? { resolution }
            : {}),
        }),
      },
    ),

  comments: (
    reportId: string,
    versionId: string,
  ) =>
    request<{
      items: ManuscriptComment[];
      total: number;
      limit: number;
      offset: number;
    }>(
      "reports/" +
        reportId +
        "/manuscript-versions/" +
        versionId +
        "/comments",
    ),

  resolveComment: (
    reportId: string,
    commentId: string,
  ) =>
    request<ManuscriptComment>(
      "reports/" +
        reportId +
        "/comments/" +
        commentId +
        "/resolve",
      {
        method: "POST",
      },
    ),

  reopenComment: (
    reportId: string,
    commentId: string,
  ) =>
    request<ManuscriptComment>(
      "reports/" +
        reportId +
        "/comments/" +
        commentId +
        "/reopen",
      {
        method: "POST",
      },
    ),
  addProjectMember: (
    projectId: string,
    body: {
      user_id: string;
      role: string;
    },
  ) =>
    request<ProjectMember>(
      "projects/" +
        projectId +
        "/members",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  changeProjectMemberRole: (
    projectId: string,
    memberId: string,
    role: string,
  ) =>
    request<ProjectMember>(
      "projects/" +
        projectId +
        "/members/" +
        memberId,
      {
        method: "PATCH",
        body: JSON.stringify({
          role,
        }),
      },
    ),

  removeProjectMember: (
    projectId: string,
    memberId: string,
  ) =>
    request<null>(
      "projects/" +
        projectId +
        "/members/" +
        memberId,
      {
        method: "DELETE",
      },
    ),

  manuscriptVersions: (
    reportId: string,
    manuscriptId: string,
    limit = 100,
    offset = 0,
  ) =>
    request<{
      items: Array<
        Schema["app__schemas__collaboration__ManuscriptVersionRead"]
      >;
      total: number;
      limit: number;
      offset: number;
    }>(
      "reports/" +
        reportId +
        "/manuscripts/" +
        manuscriptId +
        "/versions?limit=" +
        encodeURIComponent(
          String(limit),
        ) +
        "&offset=" +
        encodeURIComponent(
          String(offset),
        ),
    ),

  branches: (
    reportId: string,
    manuscriptId: string,
    limit = 100,
    offset = 0,
  ) =>
    request<{
      items: Schema["ManuscriptBranchRead"][];
      total: number;
      limit: number;
      offset: number;
    }>(
      "reports/" +
        reportId +
        "/manuscripts/" +
        manuscriptId +
        "/branches?limit=" +
        encodeURIComponent(
          String(limit),
        ) +
        "&offset=" +
        encodeURIComponent(
          String(offset),
        ),
    ),

  createBranch: (
    reportId: string,
    body: {
      manuscript_id: string;
      name: string;
      head_version_id: string;
      is_default?: boolean;
    },
  ) =>
    request<Schema["ManuscriptBranchRead"]>(
      "reports/" +
        reportId +
        "/manuscript-branches",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  mergeBranches: (
    reportId: string,
    body: {
      source_branch_id: string;
      target_branch_id: string;
      new_version_id: string;
      note?: string | null;
    },
  ) =>
    request<Schema["ManuscriptBranchRead"]>(
      "reports/" +
        reportId +
        "/manuscript-branches/merge",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  createComment: (
    reportId: string,
    versionId: string,
    body: {
      body: string;
      manuscript_section_id?: string | null;
      parent_comment_id?: string | null;
      anchor?: Record<string, unknown> | null;
    },
  ) =>
    request<ManuscriptComment>(
      "reports/" +
        reportId +
        "/manuscript-versions/" +
        versionId +
        "/comments",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  createReviewTask: (
    reportId: string,
    versionId: string,
    body: {
      manuscript_version_id: string;
      title: string;
      description?: string | null;
      severity?: string;
      assignee_user_id?: string | null;
      scope?: Record<string, unknown> | null;
      related_section_id?: string | null;
      related_qa_finding_id?: string | null;
      related_citation_id?: string | null;
      due_at?: string | null;
    },
  ) =>
    request<ManuscriptReviewTask>(
      "reports/" +
        reportId +
        "/manuscript-versions/" +
        versionId +
        "/reviews",
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