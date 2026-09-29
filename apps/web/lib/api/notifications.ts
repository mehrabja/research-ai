import type { components } from "./schema";
import { api } from "./client";
import { apiErrorFromUnknown } from "./errors";

export type NotificationPreferenceRead =
  components["schemas"]["NotificationPreferenceRead"];

export type NotificationListResponse =
  components["schemas"]["NotificationListResponse"];

export async function getNotificationPreferences(): Promise<NotificationPreferenceRead> {
  const { data, error } = await api.GET(
    "/api/v1/notifications/preferences",
  );

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      fallback: "Notification preferences request failed.",
    });
  }

  return data;
}

export async function updateNotificationPreferences(
  preferences: Record<string, boolean>,
): Promise<NotificationPreferenceRead> {
  const { data, error } = await api.PATCH(
    "/api/v1/notifications/preferences",
    {
      body: { preferences },
    },
  );

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      fallback: "Notification preferences update failed.",
    });
  }

  return data;
}

export async function listNotifications(
  workspaceId?: string,
): Promise<NotificationListResponse> {
  const { data, error } = await api.GET("/api/v1/notifications", {
    params: {
      query: {
        workspace_id: workspaceId,
        unread_only: false,
        limit: 50,
        offset: 0,
      },
    },
  });

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      fallback: "Notifications request failed.",
    });
  }

  return data;
}

export async function markNotificationRead(
  notificationId: string,
): Promise<components["schemas"]["NotificationRead"]> {
  const { data, error } = await api.POST(
    "/api/v1/notifications/{notification_id}/read",
    {
      params: { path: { notification_id: notificationId } },
    },
  );

  if (error || !data) {
    throw apiErrorFromUnknown(error, {
      fallback: "Mark notification as read failed.",
    });
  }

  return data;
}

export async function markAllNotificationsRead(
  workspaceId?: string,
): Promise<void> {
  const { error } = await api.POST(
    "/api/v1/notifications/read-all",
    {
      params: {
        query: { workspace_id: workspaceId },
      },
    },
  );

  if (error) {
    throw apiErrorFromUnknown(error, {
      fallback: "Mark all notifications as read failed.",
    });
  }
}
