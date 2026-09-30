"use client";

import type { Metadata } from "next";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createInvitation,
  listInvitations,
  listMembers,
  revokeInvitation,
  type WorkspaceInvitation,
} from "@/lib/api/team";
import { useResearchContext } from "@/lib/research-context";

export const metadata: Metadata = {
  title: "Team · Research AI",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return (name.slice(0, 2) || "U").toUpperCase();
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
}

function invitationStateTag(state: string): string {
  if (state === "pending") return "warn";
  if (state === "accepted") return "success";
  if (state === "revoked" || state === "expired") return "danger";
  return "";
}

export default function TeamPage() {
  const queryClient = useQueryClient();
  const {
    user,
    workspace,
    workspaceId,
    workspaceRole,
    workspacesQuery,
  } = useResearchContext();

  const [inviteOpen, setInviteOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "member" | "viewer">("member");
  const [createdLink, setCreatedLink] = useState("");

  const membersQuery = useQuery({
    queryKey: ["team-members", workspaceId],
    queryFn: () => listMembers(workspaceId!),
    enabled: Boolean(workspaceId),
    staleTime: 10_000,
  });

  const invitationsQuery = useQuery({
    queryKey: ["workspace-invitations", workspaceId],
    queryFn: () => listInvitations(workspaceId!),
    enabled: Boolean(workspaceId),
    staleTime: 10_000,
  });

  const create = useMutation({
    mutationFn: () => {
      if (!workspaceId) throw new Error("No workspace is selected.");
      if (!email.trim()) throw new Error("Enter an email address.");
      return createInvitation(workspaceId, email.trim(), role);
    },
    onSuccess: async (result) => {
      const link = `${window.location.origin}/invite?token=${encodeURIComponent(result.token)}`;
      setCreatedLink(link);
      setEmail("");
      await queryClient.invalidateQueries({
        queryKey: ["workspace-invitations", workspaceId],
      });
    },
  });

  const revoke = useMutation({
    mutationFn: (invitation: WorkspaceInvitation) => {
      if (!workspaceId) throw new Error("No workspace is selected.");
      return revokeInvitation(workspaceId, invitation.id);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["workspace-invitations", workspaceId],
      });
    },
  });

  const activeInvites = useMemo(
    () =>
      (invitationsQuery.data ?? []).filter(
        (item) => item.state === "pending",
      ),
    [invitationsQuery.data],
  );

  const canManageMembers =
    workspaceRole === "owner" || workspaceRole === "admin";

  if (workspacesQuery.isPending || !workspaceId) {
    return (
      <section className="card pad">
        <h1>Team & members</h1>
        <p className="muted" style={{ marginTop: 8 }}>
          Select a workspace to manage its members.
        </p>
      </section>
    );
  }

  const members = membersQuery.data ?? [];
  const loading = membersQuery.isPending || invitationsQuery.isPending;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Workspace team</div>
          <h1>{workspace?.name ?? "Team & members"}</h1>
          <p>
            Manage the real members and invitations in the selected workspace.
          </p>
        </div>
        <div className="actions">
          {canManageMembers && (
            <button
              className="btn primary"
              type="button"
              onClick={() => {
                setInviteOpen((value) => !value);
                setCreatedLink("");
                create.reset();
              }}
            >
              {inviteOpen ? "Close invite" : "Invite member"}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-4">
        <div className="card metric">
          <div className="label">Members</div>
          <div className="value">{members.length}</div>
          <div className="delta">Live workspace records</div>
        </div>
        <div className="card metric">
          <div className="label">Active members</div>
          <div className="value">
            {members.filter((member) => member.status === "active").length}
          </div>
          <div className="delta">Current memberships</div>
        </div>
        <div className="card metric">
          <div className="label">Pending invites</div>
          <div className="value">{activeInvites.length}</div>
          <div className="delta">Awaiting acceptance</div>
        </div>
        <div className="card metric">
          <div className="label">Your role</div>
          <div className="value" style={{ textTransform: "capitalize" }}>
            {workspaceRole ?? "—"}
          </div>
          <div className="delta">{user.email}</div>
        </div>
      </div>

      {inviteOpen && canManageMembers && (
        <section className="card pad" style={{ marginTop: 16 }}>
          <div className="row">
            <div>
              <h2>Invite a real teammate</h2>
              <p className="muted small" style={{ marginTop: 4 }}>
                The invitation is stored in this workspace. When an email
                provider is configured, the invitation email is sent
                automatically.
              </p>
            </div>
          </div>

          <div className="grid grid-3" style={{ marginTop: 14 }}>
            <div className="field">
              <label htmlFor="invite-email">Email address</label>
              <input
                id="invite-email"
                className="input"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="colleague@lab.edu"
                disabled={create.isPending}
              />
            </div>

            <div className="field">
              <label htmlFor="invite-role">Role</label>
              <select
                id="invite-role"
                className="input"
                value={role}
                onChange={(event) =>
                  setRole(
                    event.target.value as "admin" | "member" | "viewer",
                  )
                }
                disabled={create.isPending}
              >
                <option value="member">Member</option>
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            <div style={{ display: "flex", alignItems: "end" }}>
              <button
                className="btn primary"
                type="button"
                disabled={create.isPending || !email.trim()}
                onClick={() => create.mutate()}
              >
                {create.isPending ? "Creating…" : "Create invitation"}
              </button>
            </div>
          </div>

          {create.error && (
            <p className="muted" role="alert" style={{ marginTop: 12 }}>
              {create.error.message}
            </p>
          )}

          {createdLink && (
            <div
              className="quote-card"
              style={{ marginTop: 14 }}
            >
              <div className="strong small">Invitation created</div>
              <p className="muted small" style={{ marginTop: 5 }}>
                Email delivery is optional in this environment. Share this
                one-time invitation link with the invited person.
              </p>
              <div
                className="input"
                style={{
                  marginTop: 8,
                  wordBreak: "break-all",
                  lineHeight: 1.5,
                }}
              >
                {createdLink}
              </div>
              <button
                className="btn"
                type="button"
                style={{ marginTop: 8 }}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(createdLink);
                  } catch {
                    // Clipboard permission is optional; the link remains visible.
                  }
                }}
              >
                Copy invitation link
              </button>
            </div>
          )}
        </section>
      )}

      <section className="card table-wrap" style={{ marginTop: 16 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Member</th>
              <th>Role</th>
              <th>Status</th>
              <th>Joined</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const display = member.full_name?.trim() || member.email || member.user_id;
              return (
                <tr key={member.id}>
                  <td>
                    <div className="row" style={{ justifyContent: "flex-start" }}>
                      <div className="avatar">{initials(display)}</div>
                      <div>
                        <div className="strong">{display}</div>
                        <div className="meta">
                          {member.email ?? member.user_id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td style={{ textTransform: "capitalize" }}>{member.role}</td>
                  <td>
                    <span className={"tag " + (member.status === "active" ? "success" : "")}>
                      {member.status}
                    </span>
                  </td>
                  <td>{formatDate(member.created_at)}</td>
                </tr>
              );
            })}
            {!loading && members.length === 0 && (
              <tr>
                <td colSpan={4}>
                  <div className="empty">No members are available for this workspace.</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row">
          <div>
            <h2>Pending invitations</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Real invitations currently stored for this workspace.
            </p>
          </div>
          <span className="tag">{activeInvites.length}</span>
        </div>

        <div className="list" style={{ marginTop: 12 }}>
          {(invitationsQuery.data ?? []).map((invitation) => (
            <div className="list-item" key={invitation.id}>
              <div className="row">
                <div style={{ minWidth: 0 }}>
                  <div className="strong">{invitation.email}</div>
                  <div className="meta">
                    {invitation.role} · expires {formatDate(invitation.expires_at)}
                  </div>
                </div>
                <div className="actions">
                  <span className={"tag " + invitationStateTag(invitation.state)}>
                    {invitation.state}
                  </span>
                  {canManageMembers && invitation.state === "pending" && (
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={revoke.isPending}
                      onClick={() => revoke.mutate(invitation)}
                    >
                      {revoke.isPending ? "Revoking…" : "Revoke"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}

          {!loading && (invitationsQuery.data?.length ?? 0) === 0 && (
            <div className="empty">
              <div className="big">∅</div>
              <div>No invitations have been created for this workspace.</div>
            </div>
          )}
        </div>

        {revoke.error && (
          <p className="muted" role="alert" style={{ marginTop: 10 }}>
            {revoke.error.message}
          </p>
        )}
      </section>
    </>
  );
}
