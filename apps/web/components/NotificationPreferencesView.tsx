"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  getNotificationPreferences,
  updateNotificationPreferences,
} from "@/lib/api/notifications";

const PREFERENCES = [
  {
    key: "member_invited",
    title: "Workspace invitations",
    description: "Notify when a workspace invitation is created for your account.",
  },
  {
    key: "invitation_accepted",
    title: "Invitation acceptance",
    description: "Notify when an invitation you created is accepted.",
  },
];

export function NotificationPreferencesView() {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);

  const preferencesQuery = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: getNotificationPreferences,
  });

  const update = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: (data) => {
      queryClient.setQueryData(["notification-preferences"], data);
      setNotice("Notification preferences saved.");
    },
  });

  const preferences = preferencesQuery.data?.preferences ?? {};
  const error =
    preferencesQuery.error ??
    update.error ??
    null;

  return (
    <section className="card pad" style={{ marginTop: 16 }}>
      <div className="row">
        <div>
          <h3>Notification preferences</h3>
          <div className="muted small">
            Preferences are persisted per account and control notification event delivery.
          </div>
        </div>
      </div>

      {notice && (
        <div className="muted small" role="status" style={{ marginTop: 10 }}>
          {notice}
        </div>
      )}

      {error instanceof Error && (
        <div className="muted small" role="alert" style={{ marginTop: 10 }}>
          {error.message}
        </div>
      )}

      <div className="stack" style={{ marginTop: 14 }}>
        {PREFERENCES.map((item) => {
          const checked = preferences[item.key] ?? true;
          return (
            <label className="list-item row" key={item.key} style={{ cursor: "pointer" }}>
              <div>
                <strong>{item.title}</strong>
                <div className="muted small" style={{ marginTop: 4 }}>
                  {item.description}
                </div>
              </div>
              <input
                type="checkbox"
                aria-label={item.title}
                checked={checked}
                disabled={preferencesQuery.isPending || update.isPending}
                onChange={(event) => {
                  const next = {
                    ...preferences,
                    [item.key]: event.target.checked,
                  };
                  update.mutate(next);
                }}
              />
            </label>
          );
        })}
      </div>
    </section>
  );
}
