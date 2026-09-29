import { describe, expect, it } from "vitest";
import {
  buildContextHref,
  type ResearchContextIds,
} from "./research-context";

const ids: ResearchContextIds = {
  workspaceId: "ws-1",
  projectId: "project-2",
  reportId: "report-7",
};

describe("research context URL helpers", () => {
  it("adds the active context to a plain internal route", () => {
    expect(
      buildContextHref("/evidence", "", ids),
    ).toBe(
      "/evidence?workspaceId=ws-1&projectId=project-2&reportId=report-7",
    );
  });

  it("preserves route-specific query parameters", () => {
    expect(
      buildContextHref(
        "/literature?screening=included",
        "",
        ids,
      ),
    ).toBe(
      "/literature?screening=included&workspaceId=ws-1&projectId=project-2&reportId=report-7",
    );
  });

  it("drops child context when the destination changes project", () => {
    expect(
      buildContextHref(
        "/manuscript?projectId=project-9",
        "",
        ids,
      ),
    ).toBe(
      "/manuscript?projectId=project-9&workspaceId=ws-1",
    );
  });

  it("drops project and report when the destination changes workspace", () => {
    expect(
      buildContextHref(
        "/workspace?workspaceId=ws-9",
        "",
        ids,
      ),
    ).toBe("/workspace?workspaceId=ws-9");
  });

  it("does not leak the current report into an explicit project route", () => {
    expect(
      buildContextHref(
        "/research?projectId=project-9&mode=new",
        "",
        ids,
      ),
    ).toBe(
      "/research?projectId=project-9&mode=new&workspaceId=ws-1",
    );
  });
});
