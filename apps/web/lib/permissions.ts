import type { components } from "@/lib/api/schema";

export type WorkspaceRole = components["schemas"]["WorkspaceListItem"]["role"];
export type ManagedMemberRole = "admin" | "member" | "viewer";

export function canManageMembers(role: WorkspaceRole | null): boolean {
  return role === "owner" || role === "admin";
}

export function canManageWorkspaceLifecycle(
  role: WorkspaceRole | null,
): boolean {
  return role === "owner";
}

export function canChangeMemberRole(
  actorRole: WorkspaceRole | null,
  targetRole: string,
): boolean {
  if (actorRole === "owner") {
    return targetRole !== "owner";
  }
  if (actorRole === "admin") {
    return targetRole === "member" || targetRole === "viewer";
  }
  return false;
}

export function canRemoveMember(
  actorRole: WorkspaceRole | null,
  targetRole: string,
): boolean {
  if (actorRole === "owner") {
    return targetRole !== "owner";
  }
  if (actorRole === "admin") {
    return targetRole === "member" || targetRole === "viewer";
  }
  return false;
}

export function roleOptionsForMember(
  actorRole: WorkspaceRole | null,
): ManagedMemberRole[] {
  if (actorRole === "owner") return ["admin", "member", "viewer"];
  if (actorRole === "admin") return ["member", "viewer"];
  return [];
}
