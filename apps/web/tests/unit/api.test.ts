import{describe,expect,it,vi}from"vitest";import{api}from"@/lib/api/client";
describe("source intelligence transport",()=>{
  it("uses typed extraction and embedding endpoints",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({source_id:"s1",status:"full_text",content_hash:null,chunk_count:3,content_type:"text/plain",content_length:12,extracted_at:null,pipeline_version:"m8.1"}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({source_id:"s1",total_chunks:3,already_current:1,embedded:2,failed:0,pending:0,profile_id:"p1",usage_input_tokens:12}),{status:200}));
    const extracted=await api.extractSource("r1","s1");
    expect(extracted.chunk_count).toBe(3);
    const embedded=await api.embedSource("r1","s1");
    expect(embedded.embedded).toBe(2);
    spy.mockRestore();
  });
});

describe("manuscript prose transport",()=>{
  it("uses the persisted prose, generate, and validation contracts",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({run:{id:"run1",project_id:"p1",report_id:"r1",manuscript_id:"m1",base_manuscript_version_id:"v1",output_manuscript_version_id:null,research_plan_id:null,section_research_run_id:null,technical_intelligence_run_id:null,citation_run_id:null,context_hash:"h",prose_version:"m28.5.1",prompt_version:"p1",generation_mode:"deterministic",provider:null,model:null,status:"completed",section_count:1,paragraph_count:1,sentence_count:1,word_count:5,warnings:null,errors:null,error_message:null,duration_ms:10,started_at:null,completed_at:null,created_at:"2026-10-04T00:00:00Z"},sections:[{id:"s1",run_id:"run1",project_id:"p1",report_id:"r1",manuscript_version_id:"v1",manuscript_section_id:"ms1",section_key:"introduction",section_type:"introduction",display_order:0,title:"Introduction",status:"completed",text:"Draft text.",char_start:0,char_end:11,word_count:2,paragraph_count:1,sentence_count:1,section_context_hash:"h",provenance:null,warnings:null,error_message:null,created_at:"2026-10-04T00:00:00Z"}]}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({status:"completed",job_id:null,run_id:"run1",context_hash:"h",section_count:1,word_count:2}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({validation_status:"valid",validation_errors:[],warnings:[]}),{status:200}));
    expect((await api.manuscriptProseCurrent("r1")).sections[0].section_key).toBe("introduction");
    expect((await api.manuscriptProseGenerate("r1",{base_manuscript_version_id:"v1",async:false,force:true})).status).toBe("completed");
    expect((await api.manuscriptProseValidate("r1")).validation_status).toBe("valid");
    expect(spy).toHaveBeenCalledTimes(3);
    spy.mockRestore();
  });
});

describe("upload transport",()=>{
  it("uses typed subscription and invoice endpoints",async()=>{
    const spy=vi.spyOn(globalThis,"fetch").mockResolvedValue(
      new Response(JSON.stringify({id:"s1",workspace_id:"w1",plan_id:"p1",plan_code:"pro",status:"active",current_period_start:null,current_period_end:null,provider:"fake",cancel_at_period_end:false,created_at:"2026-10-04T00:00:00Z"}),{status:200,headers:{"content-type":"application/json"}})
    );
    const sub=await api.subscription("w1");
    expect(sub.status).toBe("active");
    spy.mockResolvedValueOnce(new Response(JSON.stringify({items:[],total:0}),{status:200,headers:{"content-type":"application/json"}}));
    const invoices=await api.billingInvoices("w1");
    expect(invoices.total).toBe(0);
    spy.mockRestore();
  });

  it("reports upload progress without setting a JSON content type",async()=>{
    const original=globalThis.XMLHttpRequest;
    const progress:number[]=[];
    let sentBody:FormData|undefined;

    class FakeXHR{
      upload={
        loaded:0,
        total:0,
        addEventListener:(_:string,handler:(event:ProgressEvent<XMLHttpRequestEventTarget>)=>void)=>{this.progressHandler=handler;},
        removeEventListener:(_:string,_handler:(event:ProgressEvent<XMLHttpRequestEventTarget>)=>void)=>{},
      };
      progressHandler=(_event:ProgressEvent<XMLHttpRequestEventTarget>)=>{};
      status=201;
      responseText=JSON.stringify({
        id:"f1",
        project_id:"p1",
        folder_id:null,
        original_filename:"paper.pdf",
        normalized_filename:"paper.pdf",
        extension:".pdf",
        sha256:"a".repeat(64),
        client_mime_type:"application/pdf",
        detected_mime_type:"application/pdf",
        size_bytes:7,
        status:"uploaded",
        extraction_status:"pending",
        extraction_error:null,
        extraction_pipeline_version:null,
        file_kind:"pdf",
        created_at:"2026-10-04T00:00:00Z",
        updated_at:"2026-10-04T00:00:00Z",
        deleted_at:null,
      });
      withCredentials=false;
      headers=new Map<string,string>();
      private listeners=new Map<string,()=>void>();

      open(method:string,url:string,_async:boolean){
        expect(method).toBe("POST");
        expect(url).toContain("/api/backend/projects/p1/files");
      }
      setRequestHeader(name:string,value:string){
        expect(["Accept","X-CSRF-Token"]).toContain(name);
        expect(name.toLowerCase()).not.toBe("content-type");
        this.headers.set(name,value);
      }
      getResponseHeader(name:string){
        return name==="content-type"?"application/json":name==="X-Request-ID"?"rid-upload":null;
      }
      addEventListener(name:string,handler:()=>void){this.listeners.set(name,handler);}
      send(body:FormData){
        sentBody=body;
        expect(body.get("file")).toBeInstanceOf(File);
        this.upload.total=7;
        this.upload.loaded=7;
        this.progressHandler({total:7,loaded:7} as ProgressEvent<XMLHttpRequestEventTarget>);
        this.listeners.get("load")?.();
      }
      abort(){this.listeners.get("abort")?.();}
    }

    Object.defineProperty(globalThis,"XMLHttpRequest",{value:FakeXHR,writable:true});
    try{
      const file=new File(["pdfdata"],"paper.pdf",{type:"application/pdf"});
      const result=await api.uploadFile("p1",file,{onProgress:value=>progress.push(value.percent)});
      expect(result.id).toBe("f1");
      expect(progress).toEqual([100]);
      expect(sentBody?.get("file")).toBeInstanceOf(File);
    }finally{
      Object.defineProperty(globalThis,"XMLHttpRequest",{value:original,writable:true});
    }
  });
});

describe("api client",()=>{it("uses same-origin proxy and propagates backend errors",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({detail:"denied"}),{status:403}));await expect(api.workspaces()).rejects.toThrow("denied");expect(spy).toHaveBeenCalledWith("/api/backend/workspaces",expect.objectContaining({cache:"no-store"}));spy.mockRestore()});it("keeps JSON transport for ordinary requests",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({items:[],total:0}),{status:200,headers:{"content-type":"application/json"}}));await api.workspaces();const init=spy.mock.calls[0]?.[1] as RequestInit;expect(new Headers(init.headers).get("content-type")).toBeNull();spy.mockRestore()});it("patches a project through the workspace-scoped endpoint",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({id:"p1",name:"Updated"}),{status:200,headers:{"content-type":"application/json"}}));await api.updateProject("p1","w1",{name:"Updated"});const [url,init]=spy.mock.calls[0]??[];expect(url).toBe("/api/backend/projects/p1?workspace_id=w1");expect(init?.method).toBe("PATCH");expect(JSON.parse(String((init as RequestInit).body))).toEqual({name:"Updated"});spy.mockRestore()});});


describe("evidence and manuscript workflow transport",()=>{
  it("sends evidence link create/remove requests",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({id:"link1",claim_id:"claim1",evidence_type:"m28_evidence",evidence_id:"ev1",source_id:"src1",support_level:"supports",relevance_score:0.9,provenance:{ui:"test"},created_at:"2026-10-04T00:00:00Z"}),{status:201}))
      .mockResolvedValueOnce(new Response(null,{status:204}));
    const link=await api.linkEvidence("r1","claim1",{evidence_type:"m28_evidence",evidence_id:"ev1",source_id:"src1",support_level:"supports",relevance_score:0.9,provenance:{ui:"test"}});
    expect(link.id).toBe("link1");
    await api.unlinkEvidence("r1","claim1","link1");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/evidence/claims/claim1/links");
    expect(spy.mock.calls[1]?.[0]).toBe("/api/backend/reports/r1/evidence/claims/claim1/links/link1");
    spy.mockRestore();
  });

  it("restores a manuscript version with optimistic revision",async()=>{
    const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({saved:true,conflict:false,draft:{revision:8,base_version_id:"v2",content:{sections:{introduction:"restored"}}}}),{status:200})
    );
    const result=await api.restoreManuscriptVersion("r1","v2",{expected_revision:7});
    expect(result.saved).toBe(true);
    const init=spy.mock.calls[0]?.[1] as RequestInit;
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/manuscript/versions/v2/restore");
    expect(JSON.parse(String(init.body))).toEqual({expected_revision:7});
    spy.mockRestore();
  });

  it("persists workspace notification preferences",async()=>{
    const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({id:"np1",workspace_id:"w1",channel:"in_app",preferences:{mentions:false,reviews:true},created_at:"2026-10-04T00:00:00Z",updated_at:"2026-10-04T00:00:00Z"}),{status:200})
    );
    const result=await api.updateNotificationPreferences({channel:"in_app",preferences:{mentions:false,reviews:true}},"w1");
    expect(result.preferences.reviews).toBe(true);
    const init=spy.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("PUT");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/notifications/preferences?workspace_id=w1");
    spy.mockRestore();
  });
});


describe("rag and collaboration transport",()=>{
  it("lists and loads persisted retrieval runs",async()=>{
    const run={
      id:"run1",project_id:"p1",query:"causal inference",normalized_query:"causal inference",
      query_hash:"qh",context_hash:"ch",retrieval_version:"m26",ranking_model_version:"rank1",
      status:"completed",candidate_count:4,final_result_count:2,duration_ms:42,
      started_at:"2026-10-04T00:00:00Z",completed_at:"2026-10-04T00:00:42Z",
      coverage:null,warnings:null
    };
    const response={
      status:"completed",job_id:null,run,
      results:[{rank:1,chunk_id:"c1",source_id:"s1",final_score:0.91,vector_score:null,lexical_score:0.9,graph_score:null,memory_score:null,quality_score:null,diversity_penalty:null,retrieval_stage:"lexical",retrieval_reason:["lexical"],graph_distance:null,memory_match:null}],
      coverage:null,warnings:[]
    };
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({items:[run],total:1,limit:25,offset:0}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify(response),{status:200}));
    expect((await api.ragRuns("p1")).items[0]?.id).toBe("run1");
    expect((await api.ragRun("p1","run1")).results[0]?.source_id).toBe("s1");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/projects/p1/rag/runs?limit=25&offset=0");
    expect(spy.mock.calls[1]?.[0]).toBe("/api/backend/projects/p1/rag/runs/run1");
    spy.mockRestore();
  });

  it("posts invitation acceptance through the authenticated API",async()=>{
    const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({workspace_id:"w1",user_id:"u1",role:"member",status:"active"}),{status:200})
    );
    const result=await api.acceptInvitation("invite-token");
    expect(result.workspace_id).toBe("w1");
    const init=spy.mock.calls[0]?.[1] as RequestInit;
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/invitations/invite-token/accept");
    expect(init.method).toBe("POST");
    spy.mockRestore();
  });
});

describe("AI Studio generation transport",()=>{
  it("reads the persisted generation result and provenance",async()=>{
    const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({report_id:"r1",run_id:"g1",status:"success",prompt_version:"m12.1",provider:"openrouter",model:"openai/gpt-4o-mini",input_tokens:12,output_tokens:8,language:"en",text:"Grounded result [E1].",context_hash:"a".repeat(64),evidence:[{marker:"[E1]",evidence_id:"e1"}],cited_markers:["[E1]"],created_at:"2026-10-08T00:00:00Z",completed_at:"2026-10-08T00:00:02Z"}),{status:200})
    );
    const current=await api.generationCurrent("r1");
    expect(current.status).toBe("success");
    expect(current.provider).toBe("openrouter");
    expect(current.cited_markers).toEqual(["[E1]"]);
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/generation/current");
    spy.mockRestore();
  });
});

describe("phase 2B quality transport",()=>{
  it("generates and reads persisted citations",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({status:"queued",job_id:"job1",run_id:null,context_hash:null,claim_count:null,citation_count:null,unsupported_count:null,coverage_score:null}),{status:202}))
      .mockResolvedValueOnce(new Response(JSON.stringify({run:{id:"run1",report_id:"r1",manuscript_id:null,manuscript_version_id:"v1",context_hash:"ch",m30_version:"m30",citation_style:"author_year",status:"completed",claim_count:2,citation_count:2,unsupported_count:0,mixed_support_count:0,duplicate_reference_count:0,coverage_score:1,warnings:null,error_message:null,duration_ms:10,created_at:"2026-10-08T00:00:00Z",completed_at:"2026-10-08T00:00:01Z"},claims:[]}),{status:200}));
    const queued=await api.citationsGenerate("r1",{manuscript_version_id:"v1",citation_style:"author_year",force:true,async:true});
    expect(queued.job_id).toBe("job1");
    const current=await api.citations("r1");
    expect(current.run.coverage_score).toBe(1);
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/citations/generate");
    spy.mockRestore();
  });

  it("runs academic QA and classification through persisted contracts",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({status:"completed",job_id:null,run_id:"qa1",context_hash:"ch",gate:"pass",finding_count:1,blocking_count:0}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({id:"p1",project_id:"p1",domain:{code:"cs",name:"Computer Science",confidence:0.9,source:"inferred",method:"heuristic",reason:"signals",alternatives:[]},paper_type:{code:"empirical",name:"Empirical",confidence:0.8,source:"inferred",method:"heuristic",reason:"signals",alternatives:[],secondary:[]},research_design:{code:"experimental",name:"Experimental",confidence:0.7,source:"inferred",method:"heuristic",reason:"signals",alternatives:[]},status:"completed",needs_review:false,error_message:null,classifier_version:"m1",taxonomy_version:"t1",context_meta:null,created_at:"2026-10-08T00:00:00Z",updated_at:"2026-10-08T00:00:00Z"}),{status:200}));
    const qa=await api.qaGenerate("r1",{manuscript_version_id:"v1",async:false,force:true});
    expect(qa.run_id).toBe("qa1");
    const cls=await api.classification("p1");
    expect(cls.domain.code).toBe("cs");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/academic-qa/generate");
    expect(spy.mock.calls[1]?.[0]).toBe("/api/backend/projects/p1/classification");
    spy.mockRestore();
  });
});

describe("phase 2C intelligence transport",()=>{
  it("generates and reads technical intelligence",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({status:"queued",job_id:"job-ti",run_id:null,context_hash:null,fact_count:null,result_count:null,metric_count:null}),{status:202}))
      .mockResolvedValueOnce(new Response(JSON.stringify({run:{id:"run-ti",project_id:"p1",report_id:null,context_hash:"ch",m29_version:"m29",status:"completed",fact_count:2,result_count:1,metric_count:1,warnings:null,error_message:null,duration_ms:12,created_at:"2026-10-08T00:00:00Z",completed_at:"2026-10-08T00:00:01Z"},fact_count:2,result_count:1,metric_count:1}),{status:200}));
    expect((await api.technicalIntelligenceGenerate("p1",{force:true,async:true})).job_id).toBe("job-ti");
    expect((await api.technicalIntelligence("p1")).fact_count).toBe(2);
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/projects/p1/technical-intelligence/generate");
    expect(spy.mock.calls[1]?.[0]).toBe("/api/backend/projects/p1/technical-intelligence");
    spy.mockRestore();
  });
  it("generates and reads section research",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({status:"completed",job_id:null,run_id:"sr1",context_hash:"ch",contract_hash:"ct",evidence_count:1,coverage_score:0.8,coverage_state:"partial"}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({run:{id:"sr1",project_id:"p1",report_id:"r1",manuscript_id:"m1",manuscript_version_id:"v1",manuscript_section_id:"s1",context_hash:"ch",contract_hash:"ct",m28_version:"m28",status:"completed",primary_query:"query",query_plan:{},retrieval_config:{},retrieval_run_id:null,candidate_count:2,selected_evidence_count:1,coverage_score:0.8,coverage_state:"partial",coverage_summary:null,warnings:null,error_message:null,duration_ms:8,created_at:"2026-10-08T00:00:00Z",completed_at:"2026-10-08T00:00:01Z"},evidence:[],coverage:null}),{status:200}));
    expect((await api.sectionResearchGenerate("r1","s1",{force:true,async:false})).run_id).toBe("sr1");
    expect((await api.sectionResearch("r1","s1")).run.id).toBe("sr1");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/manuscript/sections/s1/research");
    expect(spy.mock.calls[1]?.[0]).toBe("/api/backend/reports/r1/manuscript/sections/s1/research");
    spy.mockRestore();
  });
});

describe("phase 2D publication and orchestration transport",()=>{
  it("selects a publication target and reads compliance",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({id:"sel1",report_id:"r1",target_id:"t1",selected_by:"u1",selection_note:null,created_at:"2026-10-08T00:00:00Z"}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({run:{id:"pc1",project_id:"p1",report_id:"r1",manuscript_id:null,manuscript_version_id:"v1",target_id:"t1",context_hash:"ch",m33_version:"m33",rules_version:"r1",target_profile_version:"v1",status:"completed",finding_count:1,blocking_count:0,error_count:0,warning_count:1,info_count:0,gate:"pass",checklist_state:{passed:3},formatting_summary:null,warnings:null,error_message:null,duration_ms:4,created_at:"2026-10-08T00:00:00Z",completed_at:"2026-10-08T00:00:01Z"} }),{status:200}));
    const selection=await api.publicationSelect("r1",{target_id:"t1"});
    expect(selection.target_id).toBe("t1");
    const current=await api.publicationComplianceCurrent("r1");
    expect(current.run.gate).toBe("pass");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/publication-target/select");
    expect(spy.mock.calls[1]?.[0]).toBe("/api/backend/reports/r1/publication-compliance/current");
    spy.mockRestore();
  });

  it("starts orchestration and reads the current node graph",async()=>{
    const spy=vi.spyOn(globalThis,"fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({status:"queued",job_id:"job-o",run_id:null,context_hash:null,node_count:null,completed_node_count:null,failed_node_count:null}),{status:202}))
      .mockResolvedValueOnce(new Response(JSON.stringify({run:{id:"or1",project_id:"p1",report_id:"r1",user_id:"u1",goal:"Build evidence",context_hash:"ch",orchestration_version:"m35",planner_version:"p1",tool_registry_version:"t1",strategy:"research_pipeline",status:"running",current_node_key:"research",budget:{},budget_used:null,approvals_required:null,approvals_received:null,summary:null,errors:null,checkpoint_state:null,last_checkpoint_at:null,node_count:2,completed_node_count:1,failed_node_count:0,error_message:null,duration_ms:null,started_at:"2026-10-08T00:00:00Z",completed_at:null,failed_at:null,cancelled_at:null,created_at:"2026-10-08T00:00:00Z"},nodes:[]}),{status:200}));
    expect((await api.orchestrationRun("r1",{goal:"Build evidence",strategy:"research_pipeline",async:true})).job_id).toBe("job-o");
    expect((await api.orchestrationCurrent("r1")).run.current_node_key).toBe("research");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/backend/reports/r1/orchestration/run");
    expect(spy.mock.calls[1]?.[0]).toBe("/api/backend/reports/r1/orchestration/current");
    spy.mockRestore();
  });
});
