"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import type { Route } from "next";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { me, type AuthenticatedUser } from "@/lib/api/auth";
import { listWorkspaces, type Workspace } from "@/lib/api/workspaces";
import {
  listProjects,
  listProjectReports,
  type Project,
  type ProjectReport,
} from "@/lib/api/projects";
import { isApiError } from "@/lib/api/errors";
import {
  clearSessionUserCache,
  SESSION_EVENT_KEY,
  syncSessionUser,
} from "@/lib/session-cache";

export type ResearchContextIds = {
  workspaceId: string | null;
  projectId: string | null;
  reportId: string | null;
};

export type ResearchContextValue = ResearchContextIds & {
  user: AuthenticatedUser;
  workspace: Workspace | null;
  project: Project | null;
  report: ProjectReport | null;
  workspacesQuery: UseQueryResult<Workspace[], Error>;
  projectsQuery: UseQueryResult<Project[], Error>;
  reportsQuery: UseQueryResult<ProjectReport[], Error>;
  isLoading: boolean;
  error: Error | null;
  workspaceRole: Workspace["role"] | null;
  invalid: boolean;
  setWorkspace: (workspaceId: string | null) => void;
  setProject: (projectId: string | null) => void;
  setReport: (reportId: string | null) => void;
  resetContext: () => void;
  contextHref: (href: string) => Route;
};

const ResearchContext = createContext<ResearchContextValue | null>(null);

function resolveContextItem<T extends { id: string }>(
  items: T[],
  requestedId: string | null,
  autoSelectSingle = false,
): T | null {
  if (requestedId) {
    return items.find((item) => item.id === requestedId) ?? null;
  }
  return autoSelectSingle && items.length === 1 ? items[0] ?? null : null;
}

function withContext(
  href: string,
  _currentSearch: string,
  ids: ResearchContextIds,
): Route {
  const url = new URL(href, "https://research-ai.local");
  const params = new URLSearchParams(url.search);

  const targetWorkspace = params.get("workspaceId");
  const targetProject = params.get("projectId");

  const workspaceChanged =
    Boolean(targetWorkspace) && targetWorkspace !== ids.workspaceId;
  const projectChanged =
    Boolean(targetProject) && targetProject !== ids.projectId;

  if (!targetWorkspace && ids.workspaceId) {
    params.set("workspaceId", ids.workspaceId);
  }

  if (workspaceChanged) {
    params.delete("projectId");
    params.delete("reportId");
  }

  if (!workspaceChanged && !params.has("projectId") && ids.projectId) {
    params.set("projectId", ids.projectId);
  }

  if (projectChanged) {
    params.delete("reportId");
  }

  if (
    !workspaceChanged &&
    !projectChanged &&
    !params.has("reportId") &&
    ids.reportId
  ) {
    params.set("reportId", ids.reportId);
  }

  const query = params.toString();
  return (query ? `${url.pathname}?${query}` : url.pathname) as Route;
}

export function buildContextHref(
  href: string,
  currentSearch: string,
  ids: ResearchContextIds,
): Route {
  return withContext(href, currentSearch, ids);
}

function changeContextUrl(
  pathname: string,
  currentSearch: string,
  patch: Partial<ResearchContextIds>,
): Route {
  const params = new URLSearchParams(currentSearch);

  if ("workspaceId" in patch) {
    if (patch.workspaceId) params.set("workspaceId", patch.workspaceId);
    else params.delete("workspaceId");
    params.delete("projectId");
    params.delete("reportId");
  }

  if ("projectId" in patch) {
    if (patch.projectId) params.set("projectId", patch.projectId);
    else params.delete("projectId");
    params.delete("reportId");
  }

  if ("reportId" in patch) {
    if (patch.reportId) params.set("reportId", patch.reportId);
    else params.delete("reportId");
  }

  const query = params.toString();
  return (query ? `${pathname}?${query}` : pathname) as Route;
}

export function useResearchContext(): ResearchContextValue {
  const value = useContext(ResearchContext);
  if (!value) {
    throw new Error(
      "useResearchContext must be used inside ResearchContextProvider.",
    );
  }
  return value;
}

export function ResearchContextProvider({
  children,
}: {
  children: ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const currentSearch = searchParams.toString();

  const workspaceParam = searchParams.get("workspaceId");
  const projectParam = searchParams.get("projectId");
  const reportParam = searchParams.get("reportId");

  const sessionQuery = useQuery({
    queryKey: ["session", "user"],
    queryFn: me,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const refetchSession = sessionQuery.refetch;

  useEffect(() => {
    if (sessionQuery.data) {
      syncSessionUser(queryClient, String(sessionQuery.data.id));
    }
  }, [queryClient, sessionQuery.data]);

  useEffect(() => {
    if (
      sessionQuery.error &&
      isApiError(sessionQuery.error) &&
      sessionQuery.error.status === 401
    ) {
      clearSessionUserCache(queryClient);
      router.replace("/login");
    }
  }, [queryClient, router, sessionQuery.error]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const onStorage = (event: StorageEvent) => {
      if (event.key !== SESSION_EVENT_KEY || !event.newValue) return;
      try {
        const payload = JSON.parse(event.newValue) as { type?: string };
        if (payload.type === "logout") {
          clearSessionUserCache(queryClient, false);
          router.replace("/login");
        } else if (payload.type === "authenticated") {
          void refetchSession();
        }
      } catch {
        // Ignore malformed cross-tab session signals.
      }
    };

    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [queryClient, refetchSession, router]);

  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: listWorkspaces,
    enabled: Boolean(sessionQuery.data),
    staleTime: 60_000,
  });

  const workspace = useMemo(
    () =>
      resolveContextItem(
        workspacesQuery.data ?? [],
        workspaceParam,
        true,
      ),
    [workspaceParam, workspacesQuery.data],
  );

  const workspaceId = workspace?.id ?? null;
  const workspaceRole = workspace?.role ?? null;
  const invalidWorkspace =
    Boolean(workspaceParam) &&
    workspacesQuery.isSuccess &&
    workspace === null;

  const projectsQuery = useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: () => listProjects(workspaceId!),
    enabled:
      Boolean(sessionQuery.data && workspaceId) &&
      !invalidWorkspace,
    staleTime: 30_000,
  });

  const project = useMemo(
    () =>
      resolveContextItem(
        projectsQuery.data ?? [],
        projectParam,
        true,
      ),
    [projectParam, projectsQuery.data],
  );

  const projectId = project?.id ?? null;
  const invalidProject =
    Boolean(projectParam) &&
    projectsQuery.isSuccess &&
    project === null;

  const reportsQuery = useQuery({
    queryKey: ["project-reports", projectId],
    queryFn: () => listProjectReports(projectId!),
    enabled:
      Boolean(sessionQuery.data && projectId) &&
      !invalidWorkspace &&
      !invalidProject,
    staleTime: 30_000,
  });

  const report = useMemo(
    () =>
      resolveContextItem(
        reportsQuery.data ?? [],
        reportParam,
        true,
      ),
    [reportParam, reportsQuery.data],
  );

  const reportId = report?.id ?? null;
  const invalidReport =
    Boolean(reportParam) &&
    (!projectId ||
      (reportsQuery.isSuccess && report === null));

  const invalid =
    invalidWorkspace ||
    invalidProject ||
    invalidReport;

  // Context IDs are derived from the current URL when present and auto-selected
  // from singleton resources when omitted. Do not rewrite the URL here: doing so
  // during App Router transitions can race the target navigation, aborting page.goto
  // and leaving destination routes on the source pathname.

  const setWorkspace = useCallback(
    (nextWorkspaceId: string | null) => {
      if (
        nextWorkspaceId &&
        (workspacesQuery.data ?? []).every(
          (item) => item.id !== nextWorkspaceId,
        )
      ) {
        return;
      }
      router.replace(
        changeContextUrl(
          pathname,
          currentSearch,
          { workspaceId: nextWorkspaceId },
        ),
        { scroll: false },
      );
    },
    [
      currentSearch,
      pathname,
      router,
      workspacesQuery.data,
    ],
  );

  const setProject = useCallback(
    (nextProjectId: string | null) => {
      if (
        nextProjectId &&
        (projectsQuery.data ?? []).every(
          (item) => item.id !== nextProjectId,
        )
      ) {
        return;
      }
      router.replace(
        changeContextUrl(
          pathname,
          currentSearch,
          { projectId: nextProjectId },
        ),
        { scroll: false },
      );
    },
    [
      currentSearch,
      pathname,
      projectsQuery.data,
      router,
    ],
  );

  const setReport = useCallback(
    (nextReportId: string | null) => {
      if (
        nextReportId &&
        (reportsQuery.data ?? []).every(
          (item) => item.id !== nextReportId,
        )
      ) {
        return;
      }
      router.replace(
        changeContextUrl(
          pathname,
          currentSearch,
          { reportId: nextReportId },
        ),
        { scroll: false },
      );
    },
    [
      currentSearch,
      pathname,
      reportsQuery.data,
      router,
    ],
  );

  const resetContext = useCallback(() => {
    const next = new URLSearchParams(currentSearch);
    next.delete("workspaceId");
    next.delete("projectId");
    next.delete("reportId");

    const query = next.toString();
    router.replace(
      (query ? `${pathname}?${query}` : pathname) as Route,
      { scroll: false },
    );
  }, [currentSearch, pathname, router]);

  const contextHref = useCallback(
    (href: string) =>
      withContext(
        href,
        currentSearch,
        { workspaceId, projectId, reportId },
      ),
    [
      currentSearch,
      projectId,
      reportId,
      workspaceId,
    ],
  );

  const error = useMemo(() => {
    if (sessionQuery.error instanceof Error) {
      return sessionQuery.error;
    }
    if (workspacesQuery.error instanceof Error) {
      return workspacesQuery.error;
    }
    if (projectsQuery.error instanceof Error) {
      return projectsQuery.error;
    }
    if (reportsQuery.error instanceof Error) {
      return reportsQuery.error;
    }
    if (invalidWorkspace) {
      return new Error(
        "The selected workspace is no longer available.",
      );
    }
    if (invalidProject) {
      return new Error(
        "The selected project is not available in this workspace.",
      );
    }
    if (invalidReport) {
      return new Error(
        "The selected research report is not available for this project.",
      );
    }
    return null;
  }, [
    invalidProject,
    invalidReport,
    invalidWorkspace,
    projectsQuery.error,
    reportsQuery.error,
    sessionQuery.error,
    workspacesQuery.error,
  ]);

  const value = useMemo<ResearchContextValue>(
    () => ({
      user: sessionQuery.data as AuthenticatedUser,
      workspace,
      project,
      report,
      workspaceId,
      projectId,
      reportId,
      workspaceRole,
      workspacesQuery,
      projectsQuery,
      reportsQuery,
      isLoading:
        workspacesQuery.isPending ||
        projectsQuery.isPending ||
        reportsQuery.isPending,
      error,
      invalid,
      setWorkspace,
      setProject,
      setReport,
      resetContext,
      contextHref,
    }),
    [
      contextHref,
      error,
      invalid,
      project,
      projectId,
      projectsQuery,
      report,
      reportId,
      reportsQuery,
      resetContext,
      setProject,
      setReport,
      setWorkspace,
      sessionQuery.data,
      workspace,
      workspaceId,
      workspaceRole,
      workspacesQuery,
    ],
  );

  if (sessionQuery.isPending) {
    return (
      <main className="main shell-gate" aria-busy="true">
        <section className="card pad shell-gate-card">
          <div className="eyebrow">Research AI</div>
          <h1>Loading your research workspace…</h1>
          <p className="muted">
            Verifying your session and preparing your research context.
          </p>
        </section>
      </main>
    );
  }

  if (sessionQuery.error) {
    if (
      isApiError(sessionQuery.error) &&
      sessionQuery.error.status === 401
    ) {
      return (
        <main
          className="main shell-gate"
          aria-busy="true"
        >
          <section
            className="card pad shell-gate-card"
            role="status"
          >
            <h1>Redirecting to sign in…</h1>
          </section>
        </main>
      );
    }

    return (
      <main className="main shell-gate">
        <section
          className="card pad shell-gate-card"
          role="alert"
        >
          <h1>Unable to load your session</h1>
          <p className="muted">
            {sessionQuery.error instanceof Error
              ? sessionQuery.error.message
              : "Authentication service unavailable."}
          </p>
          <button
            type="button"
            className="btn primary"
            onClick={() => void sessionQuery.refetch()}
          >
            Try again
          </button>
        </section>
      </main>
    );
  }

  return (
    <ResearchContext.Provider value={value}>
      {children}
    </ResearchContext.Provider>
  );
}
