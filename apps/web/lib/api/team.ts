export type TeamMember = {
  id: string;
  user_id: string;
  email: string | null;
  full_name: string | null;
  role: "owner" | "admin" | "member" | "viewer" | string;
  status: string;
  created_at: string;
};

export type WorkspaceInvitation = {
  id: string;
  workspace_id: string;
  email: string;
  role: "admin" | "member" | "viewer" | string;
  state: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

export type CreatedInvitation = {
  invitation: WorkspaceInvitation;
  token: string;
};

export type MemberRole = "admin" | "member" | "viewer";

export type WorkspaceTransferResult = {
  id: string;
  name: string;
  slug: string;
  owner_user_id: string;
  status: string;
  created_at: string;
  updated_at: string;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      message?: unknown;
      error?: { message?: unknown } | unknown;
    };
    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.message === "string") return payload.message;
    if (
      payload.error &&
      typeof payload.error === "object" &&
      typeof (payload.error as { message?: unknown }).message === "string"
    ) {
      return (payload.error as { message: string }).message;
    }
  } catch {
    // Ignore malformed error payloads.
  }
  return fallback;
}

export async function listMembers(workspaceId: string): Promise<TeamMember[]> {
  const response = await fetch(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`,
    { credentials: "include", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new Error(await readError(response, "Unable to load members."));
  const data = (await response.json()) as { items?: TeamMember[] };
  return data.items ?? [];
}

export async function listInvitations(
  workspaceId: string,
): Promise<WorkspaceInvitation[]> {
  const response = await fetch(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/invitations`,
    { credentials: "include", headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(
      await readError(response, "Unable to load workspace invitations."),
    );
  }
  const data = (await response.json()) as {
    items?: WorkspaceInvitation[];
  };
  return data.items ?? [];
}

export async function createInvitation(
  workspaceId: string,
  email: string,
  role: MemberRole,
): Promise<CreatedInvitation> {
  const response = await fetch(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/invitations`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ email, role }),
    },
  );
  if (!response.ok) {
    throw new Error(
      await readError(response, "Unable to create the invitation."),
    );
  }
  return (await response.json()) as CreatedInvitation;
}

export async function changeMemberRole(
  workspaceId: string,
  userId: string,
  role: MemberRole,
): Promise<void> {
  const response = await fetch(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ role }),
    },
  );
  if (!response.ok) {
    throw new Error(
      await readError(response, "Unable to change this member's role."),
    );
  }
}

export async function removeMember(
  workspaceId: string,
  userId: string,
): Promise<void> {
  const response = await fetch(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`,
    {
      method: "DELETE",
      credentials: "include",
      headers: { Accept: "application/json" },
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, "Unable to remove this member."));
  }
}

export async function transferOwnership(
  workspaceId: string,
  targetUserId: string,
): Promise<WorkspaceTransferResult> {
  const response = await fetch(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/transfer-ownership`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ target_user_id: targetUserId }),
    },
  );
  if (!response.ok) {
    throw new Error(
      await readError(response, "Unable to transfer workspace ownership."),
    );
  }
  return (await response.json()) as WorkspaceTransferResult;
}

export async function revokeInvitation(
  workspaceId: string,
  invitationId: string,
): Promise<void> {
  const response = await fetch(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/invitations/${encodeURIComponent(invitationId)}`,
    {
      method: "DELETE",
      credentials: "include",
      headers: { Accept: "application/json" },
    },
  );
  if (!response.ok) {
    throw new Error(
      await readError(response, "Unable to revoke the invitation."),
    );
  }
}

export async function acceptInvitation(token: string): Promise<{
  workspace_id: string;
  user_id: string;
  role: string;
  status: string;
}> {
  const response = await fetch("/api/v1/workspaces/invitations/accept", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) {
    throw new Error(
      await readError(response, "Unable to accept this invitation."),
    );
  }
  return (await response.json()) as {
    workspace_id: string;
    user_id: string;
    role: string;
    status: string;
  };
}
