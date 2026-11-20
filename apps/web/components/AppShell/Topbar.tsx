"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiErrorFromResponse } from "@/lib/api/errors";
import { logout } from "@/lib/api/auth";
import { clearSessionUserCache } from "@/lib/session-cache";
import { queryKeys } from "@/lib/query-keys";
import { ROUTES } from "@/lib/routes";
import { useResearchContext } from "@/lib/research-context";
import { ResearchContextSwitcher } from "./ResearchContextSwitcher";
import { CommandPalette } from "@/components/CommandPalette";

type Notification = {
  id: string;
  title: string;
  body: string;
  kind: string;
  read_at: string | null;
  created_at: string;
};

type NotificationResponse = {
  items: Notification[];
  unread: number;
  total: number;
};

async function readNotifications(
  workspaceId?: string,
): Promise<NotificationResponse> {
  const params = new URLSearchParams({ limit: "10" });
  if (workspaceId) params.set("workspace_id", workspaceId);
  const response = await fetch(
    "/api/v1/notifications?" + params.toString(),
    {
      credentials: "include",
      headers: { Accept: "application/json" },
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "Unable to load notifications.",
    );
  }

  return response.json() as Promise<NotificationResponse>;
}

async function markRead(id: string): Promise<void> {
  const response = await fetch(
    "/api/v1/notifications/" + id + "/read",
    {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "Unable to mark notification as read.",
    );
  }
}

async function markAllRead(workspaceId?: string): Promise<void> {
  const params = workspaceId
    ? "?workspace_id=" + encodeURIComponent(workspaceId)
    : "";
  const response = await fetch(
    "/api/v1/notifications/read-all" + params,
    {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "Unable to mark notifications as read.",
    );
  }
}

function formatNotificationDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

function initials(email: string): string {
  const local = email.split("@")[0] ?? email;
  const clean = local.replace(
    /[^a-zA-Z0-9]/g,
    "",
  );
  return (
    clean.slice(0, 2).toUpperCase() ||
    "R"
  );
}

export function Topbar({
  onMenuClick,
  mobileMenuOpen,
}: {
  onMenuClick: () => void;
  mobileMenuOpen: boolean;
}) {
  const [notificationsOpen, setNotificationsOpen] =
    useState(false);
  const [commandOpen, setCommandOpen] =
    useState(false);
  const notificationsRef =
    useRef<HTMLDivElement | null>(null);
  const queryClient = useQueryClient();
  const router = useRouter();
  const { user, project, workspaceId, contextHref } =
    useResearchContext();

  const notificationsQuery = useQuery({
    queryKey: queryKeys.notifications(10, workspaceId),
    queryFn: () => readNotifications(workspaceId ?? undefined),
    refetchInterval: 30_000,
  });

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "k"
      ) {
        event.preventDefault();
        setCommandOpen(true);
        setNotificationsOpen(false);
      }

      if (event.key === "Escape") {
        setNotificationsOpen(false);
      }
    }

    function onPointerDown(event: PointerEvent) {
      const target = event.target;
      if (
        target instanceof Node &&
        !notificationsRef.current?.contains(target)
      ) {
        setNotificationsOpen(false);
      }
    }

    window.addEventListener(
      "keydown",
      onKeyDown,
    );
    document.addEventListener(
      "pointerdown",
      onPointerDown,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        onKeyDown,
      );
      document.removeEventListener(
        "pointerdown",
        onPointerDown,
      );
    };
  }, []);

  const notifications =
    notificationsQuery.data ?? {
      items: [],
      unread: 0,
      total: 0,
    };

  const notificationError =
    notificationsQuery.error instanceof Error
      ? notificationsQuery.error.message
      : null;

  const markReadMutation = useMutation({
    mutationFn: markRead,
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications(10, workspaceId),
      }),
  });

  const markAllReadMutation = useMutation({
    mutationFn: markAllRead,
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["notifications"],
      }),
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      clearSessionUserCache(queryClient, false);
      router.replace("/login");
    },
  });

  return (
    <>
      <header className="topbar">
        <div className="topbar-left">
          <button
            className="btn ghost mobile-menu"
            type="button"
            aria-label={
              mobileMenuOpen
                ? "Close navigation"
                : "Open navigation"
            }
            aria-expanded={mobileMenuOpen}
            aria-controls="primary-navigation"
            onClick={onMenuClick}
          >
            ☰
          </button>

          <button
            className="topbar-search"
            type="button"
            onClick={() => {
              setCommandOpen(true);
              setNotificationsOpen(false);
            }}
            aria-label="Open command palette"
          >
            <span>Search or jump…</span>
            <kbd>Ctrl K / ⌘K</kbd>
          </button>

          <ResearchContextSwitcher />
        </div>

        <div className="topbar-right">
          {project && (
            <span
              className="current-project-tag"
              title={project.name}
            >
              {project.name}
            </span>
          )}

          <Link
            className="btn ghost"
            href={contextHref(ROUTES.jobs)}
            aria-label="Open job center"
            title="Job center"
          >
            ◷
          </Link>

          <div
            ref={notificationsRef}
            style={{ position: "relative" }}
          >
            <button
              className="btn ghost"
              type="button"
              aria-label="Notifications"
              aria-expanded={notificationsOpen}
              onClick={() =>
                setNotificationsOpen(
                  (value) => !value,
                )
              }
            >
              🔔
              {notifications.unread > 0 && (
                <span
                  aria-label={
                    notifications.unread +
                    " unread notifications"
                  }
                  style={{
                    marginLeft: 6,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {notifications.unread}
                </span>
              )}
            </button>

            {notificationsOpen && (
              <div
                className="card pad notification-popover"
                role="dialog"
                aria-label="Notifications"
              >
                <div className="row">
                  <div>
                    <h3>Notifications</h3>
                    <div className="muted small">
                      {notifications.unread} unread
                    </div>
                  </div>

                  {notifications.unread > 0 && (
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={
                        markAllReadMutation.isPending
                      }
                      onClick={() =>
                        markAllReadMutation.mutate(workspaceId ?? undefined)
                      }
                    >
                      {markAllReadMutation.isPending
                        ? "Saving…"
                        : "Mark all read"}
                    </button>
                  )}
                </div>

                {notificationError && (
                  <p
                    className="hint"
                    role="alert"
                    style={{
                      color: "var(--danger)",
                    }}
                  >
                    {notificationError}
                  </p>
                )}

                <div
                  className="stack"
                  style={{ marginTop: 12 }}
                >
                  {notifications.items.map(
                    (item) => (
                      <button
                        key={item.id}
                        type="button"
                        className="list-item"
                        style={{
                          textAlign: "left",
                          border: 0,
                          background: item.read_at
                            ? "transparent"
                            : "rgba(159,169,255,.08)",
                          cursor: item.read_at
                            ? "default"
                            : "pointer",
                        }}
                        disabled={
                          Boolean(item.read_at) ||
                          markReadMutation.isPending
                        }
                        onClick={() =>
                          markReadMutation.mutate(
                            item.id,
                          )
                        }
                      >
                        <div className="row">
                          <strong>
                            {item.title}
                          </strong>
                          {!item.read_at && (
                            <span className="tag">
                              Unread
                            </span>
                          )}
                        </div>
                        <div
                          className="muted small"
                          style={{ marginTop: 4 }}
                        >
                          {item.body}
                        </div>
                        <div
                          className="muted tiny"
                          style={{ marginTop: 6 }}
                        >
                          {formatNotificationDate(
                            item.created_at,
                          )}
                        </div>
                      </button>
                    ),
                  )}

                  {notifications.items.length ===
                    0 && (
                    <div className="muted small">
                      No notifications.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <Link
            href={contextHref(ROUTES.settings)}
            className="user-chip"
            title={user.email}
          >
            <span className="avatar">
              {initials(user.email)}
            </span>
            <span className="user-chip-copy">
              <strong>{user.email}</strong>
              <span>Account settings</span>
            </span>
          </Link>

          <button
            className="btn ghost"
            type="button"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            aria-label="Sign out"
            title="Sign out"
          >
            {logoutMutation.isPending ? "…" : "↪"}
          </button>
        </div>
      </header>

      <CommandPalette
        key={commandOpen ? "command-open" : "command-closed"}
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
      />
    </>
  );
}
