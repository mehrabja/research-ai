import { describe, expect, it } from "vitest";
import { queryKeys } from "./query-keys";

describe("query key factories", () => {
  it("keeps context queries stable and scoped", () => {
    expect(queryKeys.session).toEqual(["session", "user"]);
    expect(queryKeys.workspaces).toEqual(["workspaces"]);
    expect(queryKeys.projects("workspace-a")).toEqual([
      "projects",
      "workspace-a",
    ]);
    expect(queryKeys.projectReports("project-a")).toEqual([
      "project-reports",
      "project-a",
    ]);
    expect(queryKeys.teamMembers("workspace-a")).toEqual([
      "team-members",
      "workspace-a",
    ]);
    expect(queryKeys.invitations("workspace-a")).toEqual([
      "workspace-invitations",
      "workspace-a",
    ]);
  });

  it("keeps notification and usage keys parameterized", () => {
    expect(queryKeys.notifications(10)).toEqual([
      "notifications",
      null,
      10,
    ]);
    expect(queryKeys.notifications(10, "workspace-a")).toEqual([
      "notifications",
      "workspace-a",
      10,
    ]);
    expect(queryKeys.workspaceUsage("workspace-a")).toEqual([
      "workspace-usage",
      "workspace-a",
    ]);
    expect(queryKeys.billingPlans).toEqual(["billing-plans"]);
    expect(queryKeys.workspacePlan("workspace-a")).toEqual([
      "workspace-plan",
      "workspace-a",
    ]);
    expect(queryKeys.workspaceSubscription("workspace-a")).toEqual([
      "workspace-subscription",
      "workspace-a",
    ]);
  });
});
