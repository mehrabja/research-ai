"use client";

import {useEffect,useMemo,useState} from "react";
import {useSearchParams} from "next/navigation";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {useWorkspace} from "./app-shell";

function value(v:unknown,fallback="—"):string{
  if(typeof v==="string"&&v.trim())return v;
  if(typeof v==="number"||typeof v==="boolean")return String(v);
  return fallback;
}
function State({title,description,error=false}:{title:string;description:string;error?:boolean}){
  return <div className={"state"+(error?" error":"")}><h3>{title}</h3><p>{description}</p></div>;
}
function Metric({label,value:v}:{label:string;value:unknown}){
  return <div className="card metric"><div className="label">{label}</div><div className="value">{value(v)}</div></div>;
}
function useContext(){
  const ws=useWorkspace();
  const params=useSearchParams();
  const requestedProjectId=params.get("projectId");
  const requestedReportId=params.get("reportId");
  const projects=useQuery({queryKey:["publication-projects",ws.workspaceId],queryFn:()=>api.projects(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const projectId=useMemo(()=>requestedProjectId&&projects.data?.items.some(p=>p.id===requestedProjectId)?requestedProjectId:projects.data?.items[0]?.id,[projects.data,requestedProjectId]);
  const reports=useQuery({queryKey:["publication-reports",projectId],queryFn:()=>api.projectReports(projectId!,ws.workspaceId!),enabled:Boolean(projectId&&ws.workspaceId)});
  const reportId=useMemo(()=>requestedReportId&&reports.data?.items.some(r=>r.id===requestedReportId)?requestedReportId:reports.data?.items[0]?.id,[reports.data,requestedReportId]);
  return {projectId,reportId};
}
function Context({projectId,reportId}:{projectId?:string;reportId?:string}){
  return <section className="card pad" style={{marginTop:16}}><div className="row"><div><div className="kicker">Backend context</div><div className="strong">Selected research context</div></div><span className="tag">Project {value(projectId)}{reportId?" · Report "+value(reportId):""}</span></div></section>;
}

export function PublicationScreen(){
  const {projectId,reportId}=useContext();
  const qc=useQueryClient();
  const targets=useQuery({queryKey:["publication-targets"],queryFn:()=>api.publicationTargets(),retry:false});
  const selected=useQuery({queryKey:["publication-current",reportId],queryFn:()=>api.publicationCurrent(reportId!),enabled:Boolean(reportId),retry:false});
  const manuscript=useQuery({queryKey:["publication-manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId),retry:false});
  const [targetId,setTargetId]=useState("");
  const [note,setNote]=useState("");
  useEffect(()=>{if(!targetId) setTargetId(selected.data?.target_id??"");},[selected.data?.target_id,targetId]);
  const selectTarget=useMutation({mutationFn:()=>api.publicationSelect(reportId!,{target_id:targetId,selection_note:note.trim()||null}),onSuccess:()=>{setNote("");void qc.invalidateQueries({queryKey:["publication-current",reportId]});}});
  const currentRun=useQuery({queryKey:["publication-compliance-current",reportId],queryFn:()=>api.publicationComplianceCurrent(reportId!),enabled:Boolean(reportId),retry:false});
  const findings=useQuery({queryKey:["publication-compliance-findings",reportId],queryFn:()=>api.publicationComplianceFindings(reportId!),enabled:Boolean(reportId&&currentRun.isSuccess),retry:false});
  const checklist=useQuery({queryKey:["publication-compliance-checklist",reportId],queryFn:()=>api.publicationComplianceChecklist(reportId!),enabled:Boolean(reportId&&currentRun.isSuccess),retry:false});
  const runs=useQuery({queryKey:["publication-compliance-runs",reportId],queryFn:()=>api.publicationComplianceRuns(reportId!),enabled:Boolean(reportId)});
  const [jobId,setJobId]=useState("");
  const job=useQuery({queryKey:["publication-compliance-job",jobId],queryFn:()=>api.job(jobId),enabled:Boolean(jobId),refetchInterval:3000});
  const generate=useMutation({
    mutationFn:()=>api.publicationComplianceGenerate(reportId!,{manuscript_version_id:manuscript.data!.version.id,target_id:targetId,force:true,async:true}),
    onSuccess:d=>{if(d.job_id)setJobId(d.job_id);else void Promise.all([qc.invalidateQueries({queryKey:["publication-compliance-current",reportId]}),qc.invalidateQueries({queryKey:["publication-compliance-findings",reportId]}),qc.invalidateQueries({queryKey:["publication-compliance-checklist",reportId]}),qc.invalidateQueries({queryKey:["publication-compliance-runs",reportId]})]);},
  });
  const validate=useMutation({mutationFn:()=>api.publicationComplianceValidate(reportId!)});
  useEffect(()=>{const s=job.data?.status;if(s==="completed"||s==="failed"||s==="cancelled"){setJobId("");void Promise.all([qc.invalidateQueries({queryKey:["publication-compliance-current",reportId]}),qc.invalidateQueries({queryKey:["publication-compliance-findings",reportId]}),qc.invalidateQueries({queryKey:["publication-compliance-checklist",reportId]}),qc.invalidateQueries({queryKey:["publication-compliance-runs",reportId]})]);}},[job.data?.status,qc,reportId]);
  return <><div className="page-head"><div><div className="eyebrow">Publication</div><h1>Publication Target & Compliance</h1><p>Select a publication profile and run the persisted submission compliance gate.</p></div></div><Context projectId={projectId} reportId={reportId}/>
  {!reportId?<section className="card pad" style={{marginTop:16}}><State title="No active report" description="Create a report before configuring publication compliance."/></section>:
  <><section className="card pad" style={{marginTop:16}}><div className="row"><div><h3>Publication target</h3><div className="muted small">Targets are backend-managed publication profiles.</div></div>{selected.data&&<span className="tag">Selected</span>}</div>
    {targets.isError?<State title="Publication targets unavailable" description="The target catalog could not be loaded." error/>:
    <><div className="grid grid-2" style={{marginTop:12}}><div className="field"><label>Target venue</label><select className="input" value={targetId} onChange={e=>setTargetId(e.target.value)} disabled={targets.isPending||!targets.data?.items.length}><option value="">Select target</option>{targets.data?.items.map(t=><option key={t.id} value={t.id}>{t.venue} · {t.target_code} · {t.citation_style}</option>)}</select></div><div className="field"><label>Selection note</label><input className="input" value={note} onChange={e=>setNote(e.target.value)} placeholder="Optional selection rationale"/></div></div>
    <button className="btn primary" style={{marginTop:12}} disabled={!targetId||selectTarget.isPending} onClick={()=>selectTarget.mutate()}>{selectTarget.isPending?"Saving…":"Save publication target"}</button>
    {selectTarget.isError&&<div className="notice error" style={{marginTop:10}}>{selectTarget.error instanceof Error?selectTarget.error.message:"Target selection failed."}</div>}
    {selected.data&&<div className="notice" style={{marginTop:10}}>Current target ID: {selected.data.target_id}{selected.data.selection_note?" · "+selected.data.selection_note:""}</div>}</>}
  </section>
  <section className="card pad" style={{marginTop:16}}><div className="row"><div><h3>Compliance gate</h3><div className="muted small">Runs against the selected manuscript version and target profile.</div></div>{currentRun.data&&<span className={"tag "+(currentRun.data.run.gate==="pass"?"success":"")}>{currentRun.data.run.gate??currentRun.data.run.status}</span>}</div>
    <div className="grid grid-3" style={{marginTop:12}}><Metric label="Manuscript version" value={manuscript.data?.version.version? "v"+manuscript.data.version.version:"Loading…"}/><Metric label="Target profile" value={currentRun.data?.run.target_profile_version??"Not run"}/><Metric label="Blocking findings" value={currentRun.data?.run.blocking_count??"—"}/></div>
    <button className="btn primary" style={{marginTop:12}} disabled={!targetId||!manuscript.data?.version.id||generate.isPending||Boolean(jobId)} onClick={()=>generate.mutate()}>{generate.isPending?"Queueing…":"Run compliance"}</button>
    {jobId&&<div className="notice" style={{marginTop:10}}>Job: {job.data?.status??"queued"}</div>}
    {generate.isError&&<div className="notice error" style={{marginTop:10}}>{generate.error instanceof Error?generate.error.message:"Compliance generation failed."}</div>}
    {currentRun.data&&<><button className="btn" style={{marginTop:10}} disabled={validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate compliance run"}</button>{validate.data&&<div className={"notice "+(validate.data.validation_status==="valid"?"success":"error")} style={{marginTop:10}}>Validation: {validate.data.validation_status}{validate.data.validation_errors.length?" · "+validate.data.validation_errors.join(", "):""}</div>}</>}
  </section>
  {currentRun.data&&<><section className="card pad" style={{marginTop:16}}><div className="row"><h3>Checklist</h3><span className="tag">{currentRun.data.run.gate??"—"}</span></div><pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11,marginTop:10}}>{JSON.stringify(checklist.data?.checklist_state??{},null,2)}</pre></section>
  <section className="card pad" style={{marginTop:16}}><div className="row"><h3>Findings</h3><span className="tag">{findings.data?.total??0}</span></div>{findings.data?.items.length===0?<State title="No compliance findings" description="The current run has no persisted findings."/>:<div className="list" style={{marginTop:10}}>{findings.data?.items.map(f=><div className="list-item" key={f.id}><div className="row"><div><div className="title">{f.title}</div><div className="meta">{f.category} · {f.severity} · {f.rule_id}</div></div></div><div className="muted small" style={{marginTop:5}}>{f.message}</div>{f.remediation&&<pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11,marginTop:7}}>{JSON.stringify(f.remediation,null,2)}</pre>}</div>)}</div>}</section>
  <section className="card pad" style={{marginTop:16}}><div className="row"><h3>Compliance history</h3><span className="tag">{runs.data?.total??0}</span></div>{runs.data?.items.map(r=><div className="list-item" key={r.id}><div className="row"><span>{r.status}</span><span className="tag">{r.finding_count} findings · {r.blocking_count} blocking</span></div><div className="meta">{r.target_profile_version} · {new Date(r.created_at).toLocaleString()}</div></div>)}</section></>}
  </>}
  </>;
}

export function OrchestrationScreen(){
  const {reportId,projectId}=useContext();
  const qc=useQueryClient();
  const current=useQuery({queryKey:["orchestration-current",reportId],queryFn:()=>api.orchestrationCurrent(reportId!),enabled:Boolean(reportId),retry:false});
  const runs=useQuery({queryKey:["orchestration-runs",reportId],queryFn:()=>api.orchestrationRuns(reportId!),enabled:Boolean(reportId)});
  const tools=useQuery({queryKey:["orchestration-tools",reportId],queryFn:()=>api.orchestrationTools(reportId!),enabled:Boolean(reportId),retry:false});
  const strategies=useQuery({queryKey:["orchestration-strategies",reportId],queryFn:()=>api.orchestrationStrategies(reportId!),enabled:Boolean(reportId),retry:false});
  const [goal,setGoal]=useState("");
  const [strategy,setStrategy]=useState("research_pipeline");
  const [jobId,setJobId]=useState("");
  const job=useQuery({queryKey:["orchestration-job",jobId],queryFn:()=>api.job(jobId),enabled:Boolean(jobId),refetchInterval:3000});
  const run=useMutation({mutationFn:()=>api.orchestrationRun(reportId!,{goal:goal.trim(),strategy,force:true,async:true}),onSuccess:d=>{setGoal("");if(d.job_id)setJobId(d.job_id);else void Promise.all([qc.invalidateQueries({queryKey:["orchestration-current",reportId]}),qc.invalidateQueries({queryKey:["orchestration-runs",reportId]})]);}});
  useEffect(()=>{if(strategies.data?.items.length && !strategies.data.items.some(item=>item.key===strategy))setStrategy(strategies.data.items[0].key);},[strategies.data?.items,strategy]);
  const runId=current.data?.run.id;
  const pause=useMutation({mutationFn:()=>api.orchestrationPause(reportId!,runId!),onSuccess:()=>void qc.invalidateQueries({queryKey:["orchestration-current",reportId]})});
  const cancel=useMutation({mutationFn:()=>api.orchestrationCancel(reportId!,runId!),onSuccess:()=>void qc.invalidateQueries({queryKey:["orchestration-current",reportId]})});
  const validate=useMutation({mutationFn:()=>api.orchestrationValidate(reportId!,runId!),onSuccess:()=>void qc.invalidateQueries({queryKey:["orchestration-current",reportId]})});
  const awaitingNode=current.data?.nodes.find(n=>n.status==="awaiting_approval");
  const approve=useMutation({mutationFn:()=>api.orchestrationApproveNode(reportId!,runId!,awaitingNode!.id),onSuccess:()=>void qc.invalidateQueries({queryKey:["orchestration-current",reportId]})});
  useEffect(()=>{const s=job.data?.status;if(s==="completed"||s==="failed"||s==="cancelled"){setJobId("");void Promise.all([qc.invalidateQueries({queryKey:["orchestration-current",reportId]}),qc.invalidateQueries({queryKey:["orchestration-runs",reportId]})]);}},[job.data?.status,qc,reportId]);
  return <><div className="page-head"><div><div className="eyebrow">Orchestration</div><h1>Research Orchestration</h1><p>Start durable research workflows, inspect nodes, and control execution state.</p></div></div><Context projectId={projectId} reportId={reportId}/>
  {!reportId?<section className="card pad" style={{marginTop:16}}><State title="No active report" description="Create a report before starting orchestration."/></section>:
  <><section className="card pad" style={{marginTop:16}}><div className="row"><div><h3>Start orchestration</h3><div className="muted small">The backend planner materializes the durable execution graph.</div></div></div>
    <div className="field" style={{marginTop:12}}><label>Goal</label><textarea className="input textarea" value={goal} onChange={e=>setGoal(e.target.value)} placeholder="Describe the research outcome this run should produce." style={{minHeight:120}}/></div>
    <div className="field" style={{marginTop:12}}><label>Strategy</label><select className="input" value={strategy} onChange={e=>setStrategy(e.target.value)} disabled={strategies.isPending||!strategies.data?.items.length}><option value="">Select strategy</option>{strategies.data?.items.map(item=><option key={item.key} value={item.key}>{item.key} — {item.description}</option>)}</select>{strategies.isError&&<div className="notice error" style={{marginTop:8}}>Strategy catalog unavailable; refresh before starting a run.</div>}</div>
    <button className="btn primary" style={{marginTop:12}} disabled={!goal.trim()||!strategy.trim()||run.isPending||Boolean(jobId)} onClick={()=>run.mutate()}>{run.isPending?"Queueing…":"Start orchestration"}</button>
    {jobId&&<div className="notice" style={{marginTop:10}}>Job: {job.data?.status??"queued"}</div>}
    {run.isError&&<div className="notice error" style={{marginTop:10}}>{run.error instanceof Error?run.error.message:"Orchestration failed."}</div>}
    {pause.isError&&<div className="notice error" style={{marginTop:10}}>{pause.error instanceof Error?pause.error.message:"Pause failed."}</div>}{cancel.isError&&<div className="notice error" style={{marginTop:10}}>{cancel.error instanceof Error?cancel.error.message:"Cancel failed."}</div>}
  </section>
  <section className="card pad" style={{marginTop:16}}><div className="row"><div><h3>Current run</h3><div className="muted small">{current.data?.run.goal??"No orchestration run yet."}</div></div>{current.data&&<span className={"tag "+(current.data.run.status==="completed"?"success":"")}>{current.data.run.status}</span>}</div>
    {current.isError?<State title="No current orchestration" description="Start an orchestration run to materialize nodes."/>:current.data&&<><div className="grid grid-4" style={{marginTop:12}}><Metric label="Nodes" value={current.data.run.node_count}/><Metric label="Completed" value={current.data.run.completed_node_count}/><Metric label="Failed" value={current.data.run.failed_node_count}/><Metric label="Current node" value={current.data.run.current_node_key??"—"}/></div>
      <div className="actions" style={{marginTop:12}}><button className="btn" disabled={pause.isPending||["completed","failed","cancelled","paused","awaiting_approval"].includes(current.data.run.status)} onClick={()=>pause.mutate()}>{pause.isPending?"Pausing…":"Pause"}</button><button className="btn" disabled={cancel.isPending||["completed","failed","cancelled"].includes(current.data.run.status)} onClick={()=>cancel.mutate()}>{cancel.isPending?"Cancelling…":"Cancel"}</button><button className="btn" disabled={validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate"}</button>{awaitingNode&&<button className="btn primary" disabled={approve.isPending} onClick={()=>approve.mutate()}>{approve.isPending?"Approving…":"Approve node"}</button>}</div>
      {validate.data&&<div className={"notice "+(validate.data.validation_status==="valid"?"success":"error")} style={{marginTop:10}}>Validation: {validate.data.validation_status}{validate.data.warnings.length?" · "+validate.data.warnings.join(", "):""}</div>}
      {validate.isError&&<div className="notice error" style={{marginTop:10}}>{validate.error instanceof Error?validate.error.message:"Orchestration validation failed."}</div>}
      {awaitingNode&&<div className="notice" style={{marginTop:10}}>Approval required for node <strong>{awaitingNode.node_key}</strong> before orchestration can continue.</div>}{approve.isError&&<div className="notice error" style={{marginTop:10}}>{approve.error instanceof Error?approve.error.message:"Node approval failed."}</div>}
      <div className="table-wrap" style={{marginTop:14}}><table className="table"><thead><tr><th>Seq</th><th>Node</th><th>Status</th><th>Attempt</th><th>Duration</th></tr></thead><tbody>{current.data.nodes.map(n=><tr key={n.id}><td>{n.sequence}</td><td><div>{n.node_key}</div><div className="muted tiny">{n.node_type} · {n.node_version}</div></td><td>{n.status}</td><td>{n.attempt}/{n.max_attempts}</td><td>{n.duration_ms??"—"} ms</td></tr>)}</tbody></table></div></>}
  </section>
  <div className="grid grid-2" style={{marginTop:16}}><section className="card pad"><div className="row"><h3>Run history</h3><span className="tag">{runs.data?.total??0}</span></div>{runs.data?.items.map(r=><div className="list-item" key={r.id}><div className="row"><span>{r.strategy}</span><span className="tag">{r.status}</span></div><div className="meta">{r.node_count} nodes · {r.completed_node_count} completed · {new Date(r.created_at).toLocaleString()}</div><div className="muted small" style={{marginTop:4}}>{r.goal}</div></div>)}</section>
  <section className="card pad"><div className="row"><h3>Tool registry</h3><span className="tag">{tools.data?.items.length??0}</span></div>{tools.data?.items.map(t=><div className="list-item" key={t.key}><div className="row"><div className="title">{t.key}</div><span className="tag">{t.deterministic?"Deterministic":"Non-deterministic"}</span></div><div className="meta">{t.version} · {t.permission}</div><div className="muted tiny" style={{marginTop:4}}>{t.description}</div></div>)}</section></div>
  </>}
  </>;
}
