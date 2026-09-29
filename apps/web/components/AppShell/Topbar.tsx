"use client";

import { useCallback, useEffect, useState } from "react";

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

async function readNotifications(): Promise<NotificationResponse> {
  const response = await fetch("/api/v1/notifications?limit=10", {
    credentials: "include",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Unable to load notifications.");
  return response.json() as Promise<NotificationResponse>;
}

async function markRead(id: string): Promise<void> {
  const response = await fetch("/api/v1/notifications/" + id + "/read", {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Unable to mark notification as read.");
}

async function markAllRead(): Promise<void> {
  const response = await fetch("/api/v1/notifications/read-all", {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) throw new Error("Unable to mark notifications as read.");
}

function formatNotificationDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationResponse>({
    items: [],
    unread: 0,
    total: 0,
  });
  const [notificationError, setNotificationError] = useState<string | null>(null);

  const refreshNotifications = useCallback(async () => {
    try {
      const result = await readNotifications();
      setNotifications(result);
      setNotificationError(null);
    } catch (error) {
      setNotificationError(
        error instanceof Error ? error.message : "Unable to load notifications.",
      );
    }
  }, []);

  useEffect(() => {
    void refreshNotifications();
  }, [refreshNotifications]);

  async function handleRead(id: string) {
    try {
      await markRead(id);
      await refreshNotifications();
    } catch (error) {
      setNotificationError(
        error instanceof Error ? error.message : "Unable to update notification.",
      );
    }
  }

  async function handleReadAll() {
    try {
      await markAllRead();
      await refreshNotifications();
    } catch (error) {
      setNotificationError(
        error instanceof Error ? error.message : "Unable to update notifications.",
      );
    }
  }

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="btn ghost mobile-menu"
          type="button"
          aria-label="Open navigation"
          onClick={onMenuClick}
        >
          ☰
        </button>
        <input
          className="search"
          placeholder="Search papers, projects, evidence…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="tag">⌘ K</span>
      </div>

      <div className="topbar-right">
        <span className="tag success">API healthy</span>
        <div style={{ position: "relative" }}>
          <button
            className="btn ghost"
            type="button"
            aria-label="Notifications"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            🔔
            {notifications.unread > 0 && (
              <span
                aria-label={notifications.unread + " unread notifications"}
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

          {open && (
            <div
              className="card pad"
              style={{
                position: "absolute",
                right: 0,
                top: "calc(100% + 8px)",
                width: 360,
                maxWidth: "calc(100vw - 32px)",
                zIndex: 30,
              }}
            >
              <div className="row">
                <div>
                  <h3>Notifications</h3>
                  <div className="muted small">
                    {notifications.unread} unread
                  </div>
                </div>
                {notifications.unread > 0 && (
                  <button className="btn ghost" type="button" onClick={() => void handleReadAll()}>
                    Mark all read
                  </button>
                )}
              </div>

              {notificationError && (
                <p className="hint" style={{ color: "var(--danger)" }}>
                  {notificationError}
                </p>
              )}

              <div className="stack" style={{ marginTop: 12 }}>
                {notifications.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="list-item"
                    style={{
                      textAlign: "left",
                      border: 0,
                      background: item.read_at ? "transparent" : "rgba(159,169,255,.08)",
                      cursor: item.read_at ? "default" : "pointer",
                    }}
                    onClick={() => !item.read_at && void handleRead(item.id)}
                  >
                    <div className="row">
                      <strong>{item.title}</strong>
                      {!item.read_at && <span className="tag">Unread</span>}
                    </div>
                    <div className="muted small" style={{ marginTop: 4 }}>
                      {item.body}
                    </div>
                    <div className="muted tiny" style={{ marginTop: 6 }}>
                      {formatNotificationDate(item.created_at)}
                    </div>
                  </button>
                ))}

                {notifications.items.length === 0 && (
                  <div className="muted small">No notifications.</div>
                )}
              </div>
            </div>
          )}
        </div>
        <div className="avatar">NI</div>
      </div>
    </header>
  );
}
