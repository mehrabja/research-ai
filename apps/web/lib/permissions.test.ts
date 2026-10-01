import { describe, expect, it } from "vitest";
import {
  canManageMembers,
  canManageWorkspaceLifecycle,
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
});
