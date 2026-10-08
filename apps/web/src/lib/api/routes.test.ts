import {expect,test} from "vitest";
import {routes} from "./routes";

test("centralized routes preserve backend API paths",()=>{
  expect(routes.jobsEnqueue()).toBe("jobs");
  expect(routes.project("p/1","w 1")).toBe("projects/p%2F1?workspace_id=w+1");
  expect(routes.sources("report-1")).toBe("reports/report-1/sources");
  expect(routes.detectionGenerate("r-1","v-1")).toBe("reports/r-1/versions/v-1/detect");
  expect(routes.humanizationEnqueue("r-1")).toBe("reports/r-1/humanization/enqueue");
  expect(routes.translationEnqueue("r-1")).toBe("reports/r-1/translation/enqueue");
  expect(routes.publicationComplianceValidate("r-1")).toBe("reports/r-1/publication-compliance/validate");
  expect(routes.orchestrationCancel("r-1","run-1")).toBe("reports/r-1/orchestration/runs/run-1/cancel");
  expect(routes.ragMemory("p-1")).toBe("projects/p-1/rag/memory");
  expect(routes.fileContent("f/1")).toBe("files/f%2F1/content");
});



describe("phase 2 report workflow routes",()=>{
  it("builds approved-review and report-version routes",()=>{
    expect(routes.preTranslationReview("r 1")).toBe("reports/r%201/review/pre-translation");
    expect(routes.reportVersion("r 1","v/2")).toBe("reports/r%201/versions/v%2F2");
  });
  it("builds detection, humanization and translation result routes",()=>{
    expect(routes.detection("r","v")).toBe("reports/r/versions/v/detection");
    expect(routes.detectionGenerate("r","v")).toBe("reports/r/versions/v/detect");
    expect(routes.humanizationCurrent("r")).toBe("reports/r/humanization/current");
    expect(routes.translationCurrent("r")).toBe("reports/r/translation/current");
  });
});
