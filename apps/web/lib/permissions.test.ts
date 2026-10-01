import { describe, expect, it } from "vitest";
import {
  canChangeMemberRole,
  canManageMembers,
  canManageWorkspaceLifecycle,
  canRemoveMember,
  roleOptionsForMember,
} from "./permissions";

describe("workspace permissions", () => {
  it("allows owners and admins to manage members", () => {
    expect(canManageMembers("owner")).toBe(true);
    expect(canManageMembers("admin")).toBe(true);
    expect(canManageMembers("member")).toBe(false);
    expect(canManageMembers("viewer")).toBe(false);
    expect(canManageMembers(null)).toBe(false);
  });

  it("restricts workspace lifecycle changes to owners", () => {
    expect(canManageWorkspaceLifecycle("owner")).toBe(true);
    expect(canManageWorkspaceLifecycle("admin")).toBe(false);
    expect(canManageWorkspaceLifecycle("member")).toBe(false);
    expect(canManageWorkspaceLifecycle("viewer")).toBe(false);
    expect(canManageWorkspaceLifecycle(null)).toBe(false);
  });

  it("matches backend role-change permissions", () => {
    expect(canChangeMemberRole("owner", "admin")).toBe(true);
    expect(canChangeMemberRole("owner", "member")).toBe(true);
    expect(canChangeMemberRole("owner", "viewer")).toBe(true);
    expect(canChangeMemberRole("owner", "owner")).toBe(false);

    expect(canChangeMemberRole("admin", "member")).toBe(true);
    expect(canChangeMemberRole("admin", "viewer")).toBe(true);
    expect(canChangeMemberRole("admin", "admin")).toBe(false);
    expect(canChangeMemberRole("admin", "owner")).toBe(false);

    expect(canChangeMemberRole("member", "member")).toBe(false);
    expect(canChangeMemberRole("viewer", "viewer")).toBe(false);
    expect(canChangeMemberRole(null, "member")).toBe(false);
  });

  it("matches backend member-removal permissions", () => {
    expect(canRemoveMember("owner", "admin")).toBe(true);
    expect(canRemoveMember("owner", "member")).toBe(true);
    expect(canRemoveMember("owner", "owner")).toBe(false);

    expect(canRemoveMember("admin", "member")).toBe(true);
    expect(canRemoveMember("admin", "viewer")).toBe(true);
    expect(canRemoveMember("admin", "admin")).toBe(false);
    expect(canRemoveMember("admin", "owner")).toBe(false);

    expect(canRemoveMember("member", "member")).toBe(false);
    expect(canRemoveMember("viewer", "viewer")).toBe(false);
  });

  it("limits role choices by actor role", () => {
    expect(roleOptionsForMember("owner")).toEqual(["admin", "member", "viewer"]);
    expect(roleOptionsForMember("admin")).toEqual(["member", "viewer"]);
    expect(roleOptionsForMember("member")).toEqual([]);
    expect(roleOptionsForMember(null)).toEqual([]);
  });
});
