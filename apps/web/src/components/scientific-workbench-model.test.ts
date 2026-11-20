import {describe,expect,it} from "vitest";
import {isActiveRunStatus,isTerminalJobStatus,progressPercent} from "./scientific-workbench-model";

describe("scientific workbench state helpers",()=>{
  it("bounds node progress",()=>{
    expect(progressPercent(2,4)).toBe(50);
    expect(progressPercent(-1,4)).toBe(0);
    expect(progressPercent(5,4)).toBe(100);
    expect(progressPercent(1,0)).toBe(0);
  });
  it("recognizes terminal jobs",()=>{
    expect(isTerminalJobStatus("completed")).toBe(true);
    expect(isTerminalJobStatus("failed")).toBe(true);
    expect(isTerminalJobStatus("cancelled")).toBe(true);
    expect(isTerminalJobStatus("running")).toBe(false);
    expect(isTerminalJobStatus(undefined)).toBe(false);
  });
  it("recognizes active run states",()=>{
    for(const status of ["queued","running","paused","awaiting_approval"]) expect(isActiveRunStatus(status)).toBe(true);
    expect(isActiveRunStatus("completed")).toBe(false);
  });
});
