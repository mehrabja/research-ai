import type { components } from "@/lib/api/schema";

export type WorkspaceRole = components["schemas"]["WorkspaceListItem"]["role"];

export function canManageMembers(role: WorkspaceRole | null): boolean {
  return role === "owner" || role === "admin";
}

export function canManageWorkspaceLifecycle(
  role: WorkspaceRole | null,
): boolean {
  return role === "owner";
}
