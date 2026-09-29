import { describe, expect, it } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import {
  clearSessionUserCache,
  getKnownSessionUserId,
  syncSessionUser,
} from "./session-cache";

describe("session query cache isolation", () => {
  it("clears cache when the authenticated user changes", () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(["session", "user"], { id: "user-a" });
    queryClient.setQueryData(["workspace-usage", "tenant-a"], {
      workspace_id: "tenant-a",
    });

    expect(syncSessionUser(queryClient, "user-a")).toBe(true);
    expect(queryClient.getQueryData(["workspace-usage", "tenant-a"])).toBeUndefined();
    expect(queryClient.getQueryData(["session", "user"])).toEqual({ id: "user-a" });

    queryClient.setQueryData(["workspace-usage", "tenant-a"], {
      workspace_id: "tenant-a",
    });

    expect(syncSessionUser(queryClient, "user-a")).toBe(false);
    expect(queryClient.getQueryData(["workspace-usage", "tenant-a"])).toEqual({
      workspace_id: "tenant-a",
    });

    expect(syncSessionUser(queryClient, "user-b")).toBe(true);
    expect(queryClient.getQueryData(["workspace-usage", "tenant-a"])).toBeUndefined();
    expect(getKnownSessionUserId()).toBe("user-b");

    clearSessionUserCache(queryClient);
    expect(getKnownSessionUserId()).toBeNull();
  });
});
