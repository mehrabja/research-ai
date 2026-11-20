"use client";

import Link from "next/link";
import {useRouter,useSearchParams} from "next/navigation";
import {useEffect,useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {useWorkspace} from "./app-shell";
import {isActiveRunStatus,isTerminalJobStatus,progressPercent} from "./scientific-workbench-model";
import "./scientific-workbench.css";

function textValue(input:unknown,fallback="—"):string {
  if(typeof input==="string"&&input.trim()) return input;
  if(typeof input==="number"||typeof input==="boolean") return String(input);
  return fallback;
}
function tone(status:string|undefined):string {
  if(status==="completed"||status==="valid") return "is-success";
  if(status==="failed"||status==="cancelled"||status==="invalid") return "is-danger";
  if(status==="paused"||status==="awaiting_approval") return "is-warning";
  if(status==="running"||status==="queued") return "is-running";
  return "";
}
function Empty({title,description}:{title:string;description:string}) {
  return <div className="wb-empty"><strong>{title}</strong><p>{description}</p></div>;
}
function Heading({title,detail,action}:{title:string;detail?:string;action?:React.ReactNode}) {
  return <div className="wb-section-title"><div><h2>{title}</h2>{detail&&<p>{detail}</p>}</div>{action}</div>;
}
function Metric({title,value:metric}:{title:string;value:unknown}) {
  return <div className="wb-metric"><span>{title}</span><strong>{metric===null||metric===undefined?"—":String(metric)}</strong></div>;
}

export function ScientificWorkbench() {
  const ws=useWorkspace();
  const router=useRouter();
  const params=useSearchParams();
  const qc=useQueryClient();
  const requestedProject=params.get("projectId");
  const requestedReport=params.get("reportId");

  const projects=useQuery({
    queryKey:["wb-projects",ws.workspaceId],
    queryFn:()=>api.projects(ws.workspaceId!),
    enabled:Boolean(ws.workspaceId),
  });
  const projectId=useMemo(()=>{
    const items=projects.data?.items??[];
    return requestedProject&&items.some(item=>item.id===requestedProject)?requestedProject:items[0]?.id;
  },[projects.data,requestedProject]);
  const reports=useQuery({
    queryKey:["wb-reports",projectId,ws.workspaceId],
    queryFn:()=>api.projectReports(projectId!,ws.workspaceId!),
    enabled:Boolean(projectId&&ws.workspaceId),
  });
  const reportId=useMemo(()=>{
    const items=reports.data?.items??[];
    return requestedReport&&items.some(item=>item.id===requestedReport)?requestedReport:items[0]?.id;
  },[reports.data,requestedReport]);
  const project=projects.data?.items.find(item=>item.id===projectId);
  const report=reports.data?.items.find(item=>item.id===reportId);

  function setContext(nextProject:string,nextReport?:string) {
    const next=new URLSearchParams(params.toString());
    next.set("projectId",nextProject);
    if(nextReport) next.set("reportId",nextReport);
    else next.delete("reportId");
    router.push("/workbench?"+next.toString());
  }

  const strategies=useQuery({
    queryKey:["wb-strategies",reportId],
    queryFn:()=>api.orchestrationStrategies(reportId!),
    enabled:Boolean(reportId),
    retry:false,
  });
  const tools=useQuery({
    queryKey:["wb-tools",reportId],
    queryFn:()=>api.orchestrationTools(reportId!),
    enabled:Boolean(reportId),
    retry:false,
  });
  const current=useQuery({
    queryKey:["wb-current",reportId],
    queryFn:()=>api.orchestrationCurrent(reportId!),
    enabled:Boolean(reportId),
    retry:false,
    refetchInterval:query=>isActiveRunStatus(query.state.data?.run.status)?3000:false,
  });
  const history=useQuery({
    queryKey:["wb-history",reportId],
    queryFn:()=>api.orchestrationRuns(reportId!),
    enabled:Boolean(reportId),
  });
  const sources=useQuery({
    queryKey:["wb-sources",reportId],
    queryFn:()=>api.sources(reportId!),
    enabled:Boolean(reportId),
  });
  const graph=useQuery({
    queryKey:["wb-graph",projectId],
    queryFn:()=>api.knowledgeGraphSummary(projectId!),
    enabled:Boolean(projectId),
    retry:false,
  });

  const [goal,setGoal]=useState("");
  const [strategy,setStrategy]=useState("research_pipeline");
  const [jobId,setJobId]=useState("");
  const [selectedRunId,setSelectedRunId]=useState<string|null>(null);
  const job=useQuery({
    queryKey:["wb-job",jobId],
    queryFn:()=>api.job(jobId),
    enabled:Boolean(jobId),
    refetchInterval:2500,
  });
  const selectedRun=useQuery({
    queryKey:["wb-run",reportId,selectedRunId],
    queryFn:()=>api.orchestrationRunDetail(reportId!,selectedRunId!),
    enabled:Boolean(reportId&&selectedRunId),
    retry:false,
    refetchInterval:query=>isActiveRunStatus(query.state.data?.run.status)?3000:false,
  });

  const displayed=selectedRun.data??current.data;
  const currentSelection=!selectedRunId||selectedRunId===current.data?.run.id;
  const runId=displayed?.run.id;
  const awaiting=displayed?.nodes.find(node=>node.status==="awaiting_approval");
  const progress=progressPercent(displayed?.run.completed_node_count??0,displayed?.run.node_count??0);

  function refresh() {
    void Promise.all([
      qc.invalidateQueries({queryKey:["wb-current",reportId]}),
      qc.invalidateQueries({queryKey:["wb-history",reportId]}),
      qc.invalidateQueries({queryKey:["wb-run",reportId]}),
    ]);
  }

  const start=useMutation({
    mutationFn:()=>api.orchestrationRun(reportId!,{goal:goal.trim(),strategy,force:true,async:true}),
    onSuccess:result=>{
      setGoal("");
      setSelectedRunId(result.run_id??null);
      if(result.job_id) setJobId(result.job_id);
      refresh();
    },
  });
  const pause=useMutation({mutationFn:()=>api.orchestrationPause(reportId!,runId!),onSuccess:refresh});
  const resume=useMutation({mutationFn:()=>api.orchestrationResume(reportId!,runId!),onSuccess:refresh});
  const cancel=useMutation({mutationFn:()=>api.orchestrationCancel(reportId!,runId!),onSuccess:refresh});
  const approve=useMutation({mutationFn:()=>api.orchestrationApproveNode(reportId!,runId!,awaiting!.id),onSuccess:refresh});
  const validate=useMutation({mutationFn:()=>api.orchestrationValidate(reportId!,runId!),onSuccess:refresh});

  useEffect(()=>{
    const items=strategies.data?.items??[];
    if(items.length&&!items.some(item=>item.key===strategy)) setStrategy(items[0].key);
  },[strategies.data?.items,strategy]);

  useEffect(()=>{
    if(job.data&&isTerminalJobStatus(job.data.status)) {
      setJobId("");
      refresh();
    }
  },[job.data?.status]);

  const canPause=currentSelection&&displayed?.run.status==="running";
  const canResume=currentSelection&&displayed?.run.status==="paused";
  const canCancel=currentSelection&&isActiveRunStatus(displayed?.run.status);

  return <div className="science-workbench">
    <header className="wb-header">
      <div><div className="eyebrow">Research operations / Workbench</div><h1>Scientific Workbench</h1><p>Coordinate research workflows, inspect execution, and keep sources and knowledge in view.</p></div>
      <div className="wb-header-actions"><span className="wb-live"><i/> Backend-connected</span><Link className="btn" href={reportId?"/orchestration?projectId="+projectId+"&reportId="+reportId:"/orchestration"}>Full orchestration</Link></div>
    </header>

    <section className="wb-context card">
      <div className="wb-context-label"><span className="wb-context-icon">⌘</span><div><strong>Research context</strong><small>All actions are scoped to this project and report</small></div></div>
      <div className="wb-context-fields">
        <label><span>Project</span><select className="input" value={projectId??""} onChange={event=>setContext(event.target.value)} disabled={!projects.data?.items.length}>
          {!projects.data?.items.length&&<option value="">No projects</option>}
          {projects.data?.items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>
        <label><span>Research brief</span><select className="input" value={reportId??""} onChange={event=>projectId&&setContext(projectId,event.target.value)} disabled={!projectId||!reports.data?.items.length}>
          {!reports.data?.items.length&&<option value="">No brief</option>}
          {reports.data?.items.map(item=><option key={item.id} value={item.id}>{item.topic}</option>)}
        </select></label>
      </div>
      {project&&report&&<div className="wb-context-description">{project.domain??"General research"} · {report.output_language} · {report.status}</div>}
    </section>

    {projects.isError&&<div className="notice error">Could not load projects: {projects.error instanceof Error?projects.error.message:"Unknown error"}</div>}
    {!projects.isPending&&!projectId&&<section className="card wb-no-context"><Empty title="No project is available" description="Create a project before opening the scientific workbench."/><Link className="btn primary" href="/projects">Open projects</Link></section>}
    {projectId&&!reports.isPending&&!reportId&&<section className="card wb-no-context"><Empty title="No research brief yet" description="Create a report to unlock source context and durable agent workflows."/><Link className="btn primary" href={"/projects/"+projectId}>Set up research</Link></section>}

    {reportId&&<div className="wb-layout">
      <aside className="wb-rail">
        <section className="wb-panel">
          <Heading title="Workflow library" detail="Strategies registered by the backend"/>
          {strategies.isPending?<div className="wb-skeleton"/>:strategies.isError?<Empty title="Strategy catalog unavailable" description="Open orchestration to inspect provider or workflow errors."/>:
            <div className="wb-strategy-list">{(strategies.data?.items??[]).map(item=><button type="button" key={item.key} className={"wb-strategy "+(strategy===item.key?"selected":"")} onClick={()=>setStrategy(item.key)}>
              <span className="wb-strategy-mark">◇</span><span><strong>{item.key.replaceAll("_"," ")}</strong><small>{item.description}</small></span>{strategy===item.key&&<i/>}
            </button>)}</div>}
        </section>
        <section className="wb-panel wb-history">
          <Heading title="Recent runs" detail={(history.data?.total??0)+" persisted runs"}/>
          {history.isPending?<div className="wb-skeleton"/>:history.isError?<Empty title="History unavailable" description="Run history could not be loaded."/>:
            !(history.data?.items.length)?<Empty title="No runs yet" description="Start a workflow to create the first durable run."/>:
            <div className="wb-run-list">{history.data?.items.map(item=><button key={item.id} type="button" className={"wb-run-item "+(selectedRunId===item.id?"selected":"")} onClick={()=>setSelectedRunId(item.id)}>
              <span className="wb-run-item-top"><strong>{item.strategy.replaceAll("_"," ")}</strong><em className={tone(item.status)}>{item.status}</em></span>
              <span className="wb-run-goal">{item.goal}</span><small>{item.completed_node_count}/{item.node_count} steps · {new Date(item.created_at).toLocaleString()}</small>
            </button>)}</div>}
          {selectedRunId&&<button className="btn ghost wb-clear-selection" type="button" onClick={()=>setSelectedRunId(null)}>Return to current run</button>}
        </section>
        <nav className="wb-shortcuts" aria-label="Research modules">
          <Link href={"/research?projectId="+projectId+"&reportId="+reportId}>⌕ <span>Discovery</span></Link>
          <Link href={"/literature?projectId="+projectId+"&reportId="+reportId}>▤ <span>Literature</span></Link>
          <Link href={"/evidence?projectId="+projectId+"&reportId="+reportId}>◇ <span>Evidence matrix</span></Link>
          <Link href={"/manuscript?projectId="+projectId+"&reportId="+reportId}>▥ <span>Manuscript</span></Link>
        </nav>
      </aside>

      <main className="wb-stage">
        <section className="wb-compose card">
          <div className="wb-compose-heading"><span className="wb-agent-orbit">✦</span><div><div className="eyebrow">Research command</div><h2>What should the research team investigate?</h2><p>Describe the outcome. The selected backend strategy plans a durable workflow and records every execution step.</p></div></div>
          <textarea className="input wb-goal" value={goal} onChange={event=>setGoal(event.target.value)} placeholder="Example: Compare the methods and limitations across the selected papers, identify disagreements in the evidence, and prepare a claim-linked synthesis."/>
          <div className="wb-compose-footer"><span className="wb-selected-strategy">Strategy <strong>{strategy.replaceAll("_"," ")||"Not selected"}</strong></span>
            <button className="btn primary" type="button" disabled={!goal.trim()||!strategy||start.isPending||Boolean(jobId)} onClick={()=>start.mutate()}>{start.isPending?"Preparing workflow…":"Start research workflow"} <span>↗</span></button>
          </div>
          {jobId&&<div className="notice" style={{marginTop:12}}>Workflow preparation: {job.data?.status??"queued"}</div>}
          {start.isError&&<div className="notice error" style={{marginTop:12}}>{start.error instanceof Error?start.error.message:"Could not start the workflow."}</div>}
        </section>

        <section className="wb-panel wb-run-panel">
          <Heading title={selectedRunId?"Selected workflow":"Live workflow"} detail={displayed?.run.goal??"No workflow is selected yet"} action={displayed&&<span className={"wb-status "+tone(displayed.run.status)}>{displayed.run.status}</span>}/>
          {current.isPending?<div className="wb-skeleton"/>:selectedRunId&&selectedRun.isPending?<div className="wb-skeleton"/>:
            !displayed?<Empty title="Waiting for the first workflow" description="Start a workflow above. Its persisted steps, approvals and execution state will appear here."/>:
            <>
              <div className="wb-progress-row"><div><strong>{displayed.run.completed_node_count} of {displayed.run.node_count} steps completed</strong><small>{displayed.run.current_node_key??"Workflow status"}</small></div><strong>{progress}%</strong></div>
              <div className="wb-progress"><span style={{width:progress+"%"}}/></div>
              <div className="wb-metrics"><Metric title="Steps" value={displayed.run.node_count}/><Metric title="Completed" value={displayed.run.completed_node_count}/><Metric title="Failed" value={displayed.run.failed_node_count}/><Metric title="Duration" value={displayed.run.duration_ms===null?"—":displayed.run.duration_ms+" ms"}/></div>
              {displayed.run.error_message&&<div className="notice error">{displayed.run.error_message}</div>}
              <div className="wb-timeline">{displayed.nodes.map(node=><article className="wb-node" key={node.id}>
                <div className={"wb-node-marker "+tone(node.status)}>{node.status==="completed"?"✓":node.status==="failed"?"!":node.sequence}</div>
                <div className="wb-node-main"><div className="wb-node-heading"><strong>{node.node_key.replaceAll("_"," ")}</strong><span className={"wb-status "+tone(node.status)}>{node.status}</span></div><p>{node.node_type} · v{node.node_version} · attempt {node.attempt}/{node.max_attempts}</p>{node.error_message&&<small className="wb-node-error">{node.error_message}</small>}</div>
                <small className="wb-node-duration">{node.duration_ms===null?"—":node.duration_ms+" ms"}</small>
              </article>)}</div>
              <div className="wb-run-controls">
                <button className="btn" type="button" disabled={!canPause||pause.isPending} onClick={()=>pause.mutate()}>{pause.isPending?"Pausing…":"Pause"}</button>
                <button className="btn" type="button" disabled={!canResume||resume.isPending} onClick={()=>resume.mutate()}>{resume.isPending?"Resuming…":"Resume"}</button>
                <button className="btn" type="button" disabled={!canCancel||cancel.isPending} onClick={()=>cancel.mutate()}>{cancel.isPending?"Cancelling…":"Cancel"}</button>
                <button className="btn" type="button" disabled={!currentSelection||validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Checking…":"Validate run"}</button>
                {awaiting&&currentSelection&&<button className="btn primary" type="button" disabled={approve.isPending} onClick={()=>approve.mutate()}>{approve.isPending?"Approving…":"Approve next step"}</button>}
              </div>
              {awaiting&&<div className="notice">Human approval is required before <strong>{awaiting.node_key}</strong> can continue.</div>}
              {validate.data&&<div className={"notice "+(validate.data.validation_status==="valid"?"":"error")}>Run validation: {validate.data.validation_status}{validate.data.warnings.length?" · "+validate.data.warnings.join(", "):""}</div>}
              {(pause.isError||resume.isError||cancel.isError||approve.isError||validate.isError)&&<div className="notice error">A workflow control failed. Refresh the run state before retrying.</div>}
            </>}
        </section>
      </main>

      <aside className="wb-inspector">
        <section className="wb-panel">
          <Heading title="Research context" detail="Persisted project intelligence"/>
          {graph.isPending?<div className="wb-skeleton"/>:graph.data?<div className="wb-graph-summary">
            <span className="wb-graph-icon">⌘</span><div><strong>Knowledge graph v{graph.data.version}</strong><small>{graph.data.status} · {graph.data.graph_version}</small></div>
            <div className="wb-graph-counts"><Metric title="Nodes" value={graph.data.node_count}/><Metric title="Relations" value={graph.data.edge_count}/></div>
            <Link className="btn wb-full-button" href={"/knowledge?projectId="+projectId+"&reportId="+reportId}>Open knowledge graph</Link>
          </div>:<Empty title="Knowledge graph not built" description="Build the project graph to inspect entities and relationships."/>}
        </section>
        <section className="wb-panel">
          <Heading title="Source library" detail={(sources.data?.items.length??0)+" saved references"} action={<Link className="wb-text-link" href={"/sources?projectId="+projectId+"&reportId="+reportId}>Open library</Link>}/>
          {sources.isPending?<div className="wb-skeleton"/>:sources.isError?<Empty title="Sources unavailable" description="The report's sources could not be loaded."/>:
            !(sources.data?.items.length)?<Empty title="No sources attached" description="Discover and save papers before asking the workflow to synthesize evidence."/>:
            <div className="wb-source-list">{sources.data?.items.slice(0,6).map(source=><article className="wb-source" key={source.id}><span className="wb-source-mark">▤</span><div><strong>{source.title}</strong><small>{source.year??"Year unknown"} · {source.source_api} · {source.status}</small></div></article>)}</div>}
        </section>
        <section className="wb-panel">
          <Heading title="Tool registry" detail="Tools available to orchestration"/>
          {tools.isPending?<div className="wb-skeleton"/>:tools.isError?<Empty title="Tool registry unavailable" description="Tool capabilities could not be loaded."/>:
            <div className="wb-tool-list">{(tools.data?.items??[]).slice(0,8).map(tool=><div className="wb-tool" key={tool.key}><span className="wb-tool-mark">⌁</span><div><strong>{tool.key}</strong><small>{tool.permission} · {tool.deterministic?"Deterministic":"Model-assisted"}</small></div></div>)}
              {(tools.data?.items.length??0)>8&&<Link className="wb-text-link" href={"/orchestration?projectId="+projectId+"&reportId="+reportId}>View all {tools.data?.items.length} tools</Link>}
            </div>}
        </section>
        <section className="wb-panel wb-integrity-note"><span>Evidence integrity</span><p>Workflow completion is not scientific validation. Review claim-to-source links and run evidence and citation validators before using results in a manuscript.</p><Link href={"/evidence?projectId="+projectId+"&reportId="+reportId}>Review evidence ↗</Link></section>
      </aside>
    </div>}
  </div>;
}
