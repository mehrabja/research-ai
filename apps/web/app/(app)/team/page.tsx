"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  changeMemberRole,
  createInvitation,
  listInvitations,
  listMembers,
  removeMember,
  transferOwnership,
  revokeInvitation,
  type MemberRole,
  type WorkspaceInvitation,
} from "@/lib/api/team";
import {
  canChangeMemberRole,
  canManageMembers as canManageWorkspaceMembers,
  canRemoveMember,
  roleOptionsForMember,
} from "@/lib/permissions";
import { queryKeys } from "@/lib/query-keys";
import { useResearchContext } from "@/lib/research-context";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    const first = parts[0] ?? "";
    const last = parts[parts.length - 1] ?? "";
    return (first.charAt(0) + last.charAt(0)).toUpperCase();
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
  const [role, setRole] = useState<MemberRole>("member");
  const [createdLink, setCreatedLink] = useState("");
  const [removeConfirmUserId, setRemoveConfirmUserId] = useState<string | null>(
    null,
  );
  const [transferConfirmUserId, setTransferConfirmUserId] = useState<string | null>(
    null,
  );

  const membersQuery = useQuery({
    queryKey: queryKeys.teamMembers(workspaceId),
    queryFn: () => listMembers(workspaceId!),
    enabled: Boolean(workspaceId),
    staleTime: 10_000,
  });

  const invitationsQuery = useQuery({
    queryKey: queryKeys.invitations(workspaceId),
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
        queryKey: queryKeys.invitations(workspaceId),
      });
    },
  });

  const changeRole = useMutation({
    mutationFn: (input: { userId: string; role: MemberRole }) => {
      if (!workspaceId) throw new Error("No workspace is selected.");
      return changeMemberRole(workspaceId, input.userId, input.role);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.teamMembers(workspaceId),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.workspaces,
        }),
      ]);
    },
  });

  const remove = useMutation({
    mutationFn: (userId: string) => {
      if (!workspaceId) throw new Error("No workspace is selected.");
      return removeMember(workspaceId, userId);
    },
    onSuccess: async () => {
      setRemoveConfirmUserId(null);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.teamMembers(workspaceId),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.workspaces,
        }),
      ]);
    },
  });

  const transfer = useMutation({
    mutationFn: (targetUserId: string) => {
      if (!workspaceId) throw new Error("No workspace is selected.");
      return transferOwnership(workspaceId, targetUserId);
    },
    onSuccess: async () => {
      setTransferConfirmUserId(null);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.teamMembers(workspaceId),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.workspaces,
        }),
      ]);
    },
  });

  const revoke = useMutation({
    mutationFn: (invitation: WorkspaceInvitation) => {
      if (!workspaceId) throw new Error("No workspace is selected.");
      return revokeInvitation(workspaceId, invitation.id);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.invitations(workspaceId),
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

  const canManageMembers = canManageWorkspaceMembers(workspaceRole);
  const roleOptions = roleOptionsForMember(workspaceRole);

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
                onChange={(event) => setRole(event.target.value as MemberRole)}
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
            <div className="quote-card" style={{ marginTop: 14 }}>
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
              {canManageMembers && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const display =
                member.full_name?.trim() || member.email || member.user_id;
              const canChangeRole = canChangeMemberRole(
                workspaceRole,
                member.role,
              );
              const canRemove = canRemoveMember(workspaceRole, member.role);
              const showActions = canChangeRole || canRemove;

              return (
                <tr key={member.id}>
                  <td>
                    <div
                      className="row"
                      style={{ justifyContent: "flex-start" }}
                    >
                      <div className="avatar">{initials(display)}</div>
                      <div>
                        <div className="strong">{display}</div>
                        <div className="meta">
                          {member.email ?? member.user_id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td style={{ textTransform: "capitalize" }}>
                    {canChangeRole ? (
                      <select
                        className="input"
                        style={{ minWidth: 120 }}
                        aria-label={`Change role for ${display}`}
                        value={member.role}
                        disabled={changeRole.isPending}
                        onChange={(event) =>
                          changeRole.mutate({
                            userId: member.user_id,
                            role: event.target.value as MemberRole,
                          })
                        }
                      >
                        {roleOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : (
                      member.role
                    )}
                  </td>
                  <td>
                    <span
                      className={
                        "tag " + (member.status === "active" ? "success" : "")
                      }
                    >
                      {member.status}
                    </span>
                  </td>
                  <td>{formatDate(member.created_at)}</td>
                  {canManageMembers && (
                    <td>
                      {showActions ? (
                        <div className="actions">
                          {canRemove &&
                            (removeConfirmUserId === member.user_id ? (
                              <>
                                <button
                                  className="btn ghost"
                                  type="button"
                                  disabled={remove.isPending}
                                  onClick={() => setRemoveConfirmUserId(null)}
                                >
                                  Cancel
                                </button>
                                <button
                                  className="btn"
                                  type="button"
                                  disabled={remove.isPending}
                                  onClick={() =>
                                    remove.mutate(member.user_id)
                                  }
                                >
                                  {remove.isPending
                                    ? "Removing…"
                                    : "Confirm removal"}
                                </button>
                              </>
                            ) : (
                              <button
                                className="btn ghost"
                                type="button"
                                disabled={remove.isPending}
                                aria-label={`Remove ${display}`}
                                onClick={() =>
                                  setRemoveConfirmUserId(member.user_id)
                                }
                              >
                                Remove
                              </button>
                            ))}
                        </div>
                      ) : (
                        <span className="muted small">—</span>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
            {!loading && members.length === 0 && (
              <tr>
                <td colSpan={canManageMembers ? 5 : 4}>
                  <div className="empty">
                    No members are available for this workspace.
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {(changeRole.error || remove.error) && (
        <p className="muted" role="alert" style={{ marginTop: 10 }}>
          {changeRole.error?.message ?? remove.error?.message}
        </p>
      )}


      {workspaceRole === "owner" && (
        <section className="card pad" style={{ marginTop: 16 }}>
          <div>
            <h2>Transfer ownership</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Ownership transfers the workspace to another active member. You
              become an admin after the transfer.
            </p>
          </div>

          {members.filter(
            (member) => member.user_id !== user.id && member.role !== "owner",
          ).length === 0 ? (
            <div className="empty" style={{ marginTop: 12 }}>
              Add another active member before transferring ownership.
            </div>
          ) : (
            <div className="grid grid-3" style={{ marginTop: 14 }}>
              <div className="field">
                <label htmlFor="transfer-owner">New owner</label>
                <select
                  id="transfer-owner"
                  className="input"
                  value={transferConfirmUserId ?? ""}
                  disabled={transfer.isPending}
                  onChange={(event) =>
                    setTransferConfirmUserId(event.target.value || null)
                  }
                >
                  <option value="">Select a member</option>
                  {members
                    .filter(
                      (member) =>
                        member.user_id !== user.id && member.role !== "owner",
                    )
                    .map((member) => {
                      const display =
                        member.full_name?.trim() ||
                        member.email ||
                        member.user_id;
                      return (
                        <option key={member.user_id} value={member.user_id}>
                          {display}
                        </option>
                      );
                    })}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "end" }}>
                {transferConfirmUserId ? (
                  <div className="actions">
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={transfer.isPending}
                      onClick={() => setTransferConfirmUserId(null)}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn"
                      type="button"
                      disabled={transfer.isPending}
                      onClick={() => transfer.mutate(transferConfirmUserId)}
                    >
                      {transfer.isPending
                        ? "Transferring…"
                        : "Confirm transfer"}
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          {transfer.error && (
            <p className="muted" role="alert" style={{ marginTop: 10 }}>
              {transfer.error.message}
            </p>
          )}
        </section>
      )}

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
