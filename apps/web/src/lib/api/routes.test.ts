import {describe,expect,it,test} from "vitest";
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
  it("builds the persisted generation current route",()=>{
    expect(routes.generationCurrent("r 1")).toBe("reports/r%201/generation/current");
  });
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

describe("phase 2B quality workflow routes",()=>{
  it("builds citation and academic QA routes",()=>{
    expect(routes.citationsGenerate("r 1")).toBe("reports/r%201/citations/generate");
    expect(routes.citationsBibliography("r 1")).toBe("reports/r%201/citations/bibliography");
    expect(routes.qaGenerate("r 1")).toBe("reports/r%201/academic-qa/generate");
    expect(routes.qaFindings("r 1")).toBe("reports/r%201/academic-qa/findings");
  });
  it("builds classification routes",()=>{
    expect(routes.classification("p 1")).toBe("projects/p%201/classification");
    expect(routes.classificationRecompute("p 1")).toBe("projects/p%201/classification/recompute");
    expect(routes.classificationExplanation("p 1")).toBe("projects/p%201/classification/explanation");
  });
});

describe("phase 2C intelligence workflow routes",()=>{
  it("builds technical intelligence routes",()=>{
    expect(routes.technicalIntelligenceGenerate("p 1")).toBe("projects/p%201/technical-intelligence/generate");
    expect(routes.technicalIntelligenceValidate("p 1")).toBe("projects/p%201/technical-intelligence/validate");
    expect(routes.technicalIntelligenceMetrics("p 1")).toBe("projects/p%201/technical-intelligence/metrics");
  });
  it("builds section research routes",()=>{
    expect(routes.sectionResearchGenerate("r 1","s/1")).toBe("reports/r%201/manuscript/sections/s%2F1/research");
    expect(routes.sectionResearchRuns("r 1","s/1")).toBe("reports/r%201/manuscript/sections/s%2F1/research/runs");
    expect(routes.sectionResearchValidate("r 1","s/1")).toBe("reports/r%201/manuscript/sections/s%2F1/research/validate");
  });
});

describe("remaining backend route coverage",()=>{
  it("builds project archive, knowledge graph generation, RAG memory and workspace routes",()=>{
    expect(routes.projectArchive("p 1","w 1")).toBe("projects/p%201/archive?workspace_id=w+1");
    expect(routes.knowledgeGraphGenerate("p 1")).toBe("projects/p%201/knowledge-graph/generate");
    expect(routes.ragMemory("p 1","entity",50)).toBe("projects/p%201/rag/memory?memory_type=entity&limit=50");
    expect(routes.workspace("w 1")).toBe("workspaces/w%201");
  });
  it("builds the post-translation humanization route",()=>{
    expect(routes.postTranslationHumanization("r 1")).toBe("reports/r%201/post-translation-humanization/enqueue");
  });
});

describe("phase 2D publication and orchestration routes",()=>{
  it("builds publication routes",()=>{
    expect(routes.publicationTargets()).toBe("publication-targets");
    expect(routes.publicationSelect("r 1")).toBe("reports/r%201/publication-target/select");
    expect(routes.publicationComplianceCurrent("r 1")).toBe("reports/r%201/publication-compliance/current");
    expect(routes.publicationComplianceFindings("r 1")).toBe("reports/r%201/publication-compliance/findings");
    expect(routes.publicationComplianceValidate("r 1")).toBe("reports/r%201/publication-compliance/validate");
  });
  it("builds orchestration control routes",()=>{
    expect(routes.orchestrationRun("r 1")).toBe("reports/r%201/orchestration/run");
    expect(routes.orchestrationCurrent("r 1")).toBe("reports/r%201/orchestration/current");
    expect(routes.orchestrationCancel("r 1","run/1")).toBe("reports/r%201/orchestration/runs/run%2F1/cancel");
    expect(routes.orchestrationValidate("r 1","run/1")).toBe("reports/r%201/orchestration/runs/run%2F1/validate");
    expect(routes.orchestrationStrategies("r 1")).toBe("reports/r%201/orchestration/strategies");
    expect(routes.orchestrationApproveNode("r 1","run/1","node/1")).toBe("reports/r%201/orchestration/runs/run%2F1/nodes/node%2F1/approve");
    expect(routes.orchestrationResume("r 1","run/1")).toBe("reports/r%201/orchestration/runs/run%2F1/resume");
  });
});


describe("Agent Runtime routes",()=>{
  it("builds report-scoped session and message routes",()=>{
    expect(routes.agentRuntimeSessions("report/1")).toBe("reports/report%2F1/agent-runtime/sessions");
    expect(routes.agentRuntimeSession("report/1","session 1")).toBe("reports/report%2F1/agent-runtime/sessions/session%201");
    expect(routes.agentRuntimeMessages("report/1","session 1")).toBe("reports/report%2F1/agent-runtime/sessions/session%201/messages");
  });
  it("builds tool request, approve and reject routes",()=>{
    expect(routes.agentRuntimeToolCalls("r 1","s/1")).toBe("reports/r%201/agent-runtime/sessions/s%2F1/tool-calls");
    expect(routes.agentRuntimeToolApprove("r 1","s/1","tool 1")).toBe("reports/r%201/agent-runtime/sessions/s%2F1/tool-calls/tool%201/approve");
    expect(routes.agentRuntimeToolReject("r 1","s/1","tool 1")).toBe("reports/r%201/agent-runtime/sessions/s%2F1/tool-calls/tool%201/reject");
  });
});
