"use client";

import {useEffect,useMemo,useState} from "react";
import {useSearchParams} from "next/navigation";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {useWorkspace} from "./app-shell";

function text(v:unknown,fallback="—"):string{
  if(typeof v==="string"&&v.trim())return v;
  if(typeof v==="number"||typeof v==="boolean")return String(v);
  return fallback;
}
function State({title,description,error=false}:{title:string;description:string;error?:boolean}){
  return <div className={"state"+(error?" error":"")}><h3>{title}</h3><p>{description}</p></div>;
}
function Metric({label,value}:{label:string;value:unknown}){
  return <div className="card metric"><div className="label">{label}</div><div className="value">{text(value)}</div></div>;
}
function Context({projectId,reportId}:{projectId?:string;reportId?:string}){
  return <section className="card pad" style={{marginTop:16}}>
    <div className="row"><div><div className="kicker">Backend context</div><div className="strong">Selected research context</div></div>
      <span className="tag">Project {text(projectId)}{reportId?" · Report "+text(reportId):""}</span>
    </div>
    <div className="muted tiny" style={{marginTop:8}}>All results are loaded from persisted backend records.</div>
  </section>;
}
function useContext(){
  const ws=useWorkspace();
  const params=useSearchParams();
  const requestedProjectId=params.get("projectId");
  const requestedReportId=params.get("reportId");
  const projects=useQuery({queryKey:["intelligence-projects",ws.workspaceId],queryFn:()=>api.projects(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const projectId=useMemo(()=>requestedProjectId&&projects.data?.items.some(p=>p.id===requestedProjectId)?requestedProjectId:projects.data?.items[0]?.id,[projects.data,requestedProjectId]);
  const reports=useQuery({queryKey:["intelligence-reports",projectId],queryFn:()=>api.projectReports(projectId!,ws.workspaceId!),enabled:Boolean(projectId&&ws.workspaceId)});
  const reportId=useMemo(()=>requestedReportId&&reports.data?.items.some(r=>r.id===requestedReportId)?requestedReportId:reports.data?.items[0]?.id,[reports.data,requestedReportId]);
  return {projectId,reportId};
}

export function TechnicalIntelligenceScreen(){
  const {projectId}=useContext();
  const qc=useQueryClient();
  const current=useQuery({queryKey:["technical-current",projectId],queryFn:()=>api.technicalIntelligence(projectId!),enabled:Boolean(projectId),retry:false});
  const facts=useQuery({queryKey:["technical-facts",projectId],queryFn:()=>api.technicalIntelligenceFacts(projectId!),enabled:Boolean(projectId&&current.isSuccess),retry:false});
  const results=useQuery({queryKey:["technical-results",projectId],queryFn:()=>api.technicalIntelligenceResults(projectId!),enabled:Boolean(projectId&&current.isSuccess),retry:false});
  const metrics=useQuery({queryKey:["technical-metrics",projectId],queryFn:()=>api.technicalIntelligenceMetrics(projectId!),enabled:Boolean(projectId&&current.isSuccess),retry:false});
  const runs=useQuery({queryKey:["technical-runs",projectId],queryFn:()=>api.technicalIntelligenceRuns(projectId!),enabled:Boolean(projectId)});
  const [jobId,setJobId]=useState("");
  const job=useQuery({queryKey:["technical-job",jobId],queryFn:()=>api.job(jobId),enabled:Boolean(jobId),refetchInterval:3000});
  const generate=useMutation({mutationFn:()=>api.technicalIntelligenceGenerate(projectId!,{force:true,async:true}),onSuccess:d=>setJobId(d.job_id??"")});
  const validate=useMutation({mutationFn:()=>api.technicalIntelligenceValidate(projectId!),onSuccess:()=>void qc.invalidateQueries({queryKey:["technical-current",projectId]})});
  useEffect(()=>{
    const s=job.data?.status;
    if(s==="completed"||s==="failed"||s==="cancelled"){
      setJobId("");
      void Promise.all([
        qc.invalidateQueries({queryKey:["technical-current",projectId]}),
        qc.invalidateQueries({queryKey:["technical-facts",projectId]}),
        qc.invalidateQueries({queryKey:["technical-results",projectId]}),
        qc.invalidateQueries({queryKey:["technical-metrics",projectId]}),
        qc.invalidateQueries({queryKey:["technical-runs",projectId]})
      ]);
    }
  },[job.data?.status,qc,projectId]);
  return <>
    <div className="page-head"><div><div className="eyebrow">Technical intelligence</div><h1>Technical Intelligence</h1><p>Extract durable technical facts, experiment results and normalized metrics from project files.</p></div></div>
    <Context projectId={projectId}/>
    {!projectId?<section className="card pad" style={{marginTop:16}}><State title="No active project" description="Create a project before generating technical intelligence."/></section>:
    <>
      <section className="card pad" style={{marginTop:16}}>
        <div className="row"><div><h3>Pipeline</h3><div className="muted small">The backend owns file analysis and persisted intelligence runs.</div></div>{current.data&&<span className="tag">{current.data.run.status}</span>}</div>
        <button className="btn primary" style={{marginTop:12}} disabled={generate.isPending||Boolean(jobId)} onClick={()=>generate.mutate()}>{generate.isPending?"Queueing…":"Generate technical intelligence"}</button>
        {jobId&&<div className="notice" style={{marginTop:10}}>Job: {job.data?.status??"queued"}</div>}
        {generate.isError&&<div className="notice error" style={{marginTop:10}}>{generate.error instanceof Error?generate.error.message:"Technical intelligence generation failed."}</div>}
        {current.data&&<div className="grid grid-3" style={{marginTop:14}}><Metric label="Facts" value={current.data.fact_count}/><Metric label="Experiment results" value={current.data.result_count}/><Metric label="Metrics" value={current.data.metric_count}/></div>}
        {current.data&&<button className="btn" style={{marginTop:10}} disabled={validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate run"}</button>}
        {validate.data&&<div className={"notice "+(validate.data.validation_status==="valid"?"success":"error")} style={{marginTop:10}}>Validation: {validate.data.validation_status}{validate.data.validation_errors.length?" · "+validate.data.validation_errors.join(", "):""}</div>}
      </section>
      {current.isError?<section className="card pad" style={{marginTop:16}}><State title="No completed intelligence run" description="Generate technical intelligence to populate facts, results and metrics."/></section>:
      current.data&&<>
        <div className="grid grid-2" style={{marginTop:16}}>
          <section className="card pad"><div className="row"><h3>Technical facts</h3><span className="tag">{facts.data?.total??0}</span></div>
            {facts.data?.items.length===0?<State title="No facts" description="No durable technical facts were produced by the current run."/>:
            <div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Fact</th><th>Type</th><th>Value</th><th>Confidence</th></tr></thead><tbody>
              {facts.data?.items.map(f=><tr key={f.id}><td style={{whiteSpace:"normal",overflowWrap:"anywhere"}}>{f.fact_key}</td><td>{f.fact_type}</td><td>{f.fact_value??f.normalized_value??"—"} {f.unit??""}</td><td>{Math.round(f.confidence*100)}%</td></tr>)}
            </tbody></table></div>}
          </section>
          <section className="card pad"><div className="row"><h3>Experiment results</h3><span className="tag">{results.data?.total??0}</span></div>
            {results.data?.items.length===0?<State title="No experiment results" description="The current run has no experiment result records."/>:
            <div className="list" style={{marginTop:10}}>{results.data?.items.map(r=><div className="list-item" key={r.id}>
              <div className="row"><div className="title">{r.name}</div><span className="tag">{r.status}</span></div>
              <div className="meta">{r.result_type} · {r.experiment_key??"No experiment key"}</div>
              <div className="muted small" style={{marginTop:5}}>{r.description??"No description recorded."}</div>
              {r.value&&<pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11,marginTop:7}}>{JSON.stringify(r.value,null,2)}</pre>}
            </div>)}</div>}
          </section>
        </div>
        <section className="card pad" style={{marginTop:16}}><div className="row"><h3>Normalized metrics</h3><span className="tag">{metrics.data?.total??0}</span></div>
          {metrics.data?.items.length===0?<State title="No normalized metrics" description="The current run has no metric records."/>:
          <div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Name</th><th>Value</th><th>Split</th><th>Direction</th><th>Delta</th></tr></thead><tbody>
            {metrics.data?.items.map(m=><tr key={m.id}><td>{m.name}</td><td>{m.value_numeric??m.value_text??"—"} {m.unit??""}</td><td>{m.split??"—"}</td><td>{m.direction??"—"}</td><td>{m.delta_value??"—"}</td></tr>)}
          </tbody></table></div>}
        </section>
        <section className="card pad" style={{marginTop:16}}><div className="row"><h3>Run history</h3><span className="tag">{runs.data?.total??0}</span></div>
          {runs.data?.items.map(r=><div className="list-item" key={r.id}><div className="row"><span>{r.status}</span><span className="tag">{r.fact_count} facts · {r.result_count} results · {r.metric_count} metrics</span></div><div className="meta">{new Date(r.created_at).toLocaleString()} · {r.m29_version}</div>{r.error_message&&<div className="muted tiny" style={{marginTop:4}}>{r.error_message}</div>}</div>)}
        </section>
      </>}
    </>}
  </>;
}

export function SectionResearchScreen(){
  const {reportId}=useContext();
  const qc=useQueryClient();
  const manuscript=useQuery({queryKey:["section-research-manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId),retry:false});
  const sections=manuscript.data?.sections??[];
  const [sectionId,setSectionId]=useState("");
  useEffect(()=>{if(!sectionId&&sections[0]?.id)setSectionId(sections[0].id);},[sectionId,sections]);
  const current=useQuery({queryKey:["section-research-current",reportId,sectionId],queryFn:()=>api.sectionResearch(reportId!,sectionId),enabled:Boolean(reportId&&sectionId),retry:false});
  const runs=useQuery({queryKey:["section-research-runs",reportId,sectionId],queryFn:()=>api.sectionResearchRuns(reportId!,sectionId),enabled:Boolean(reportId&&sectionId)});
  const [jobId,setJobId]=useState("");
  const job=useQuery({queryKey:["section-research-job",jobId],queryFn:()=>api.job(jobId),enabled:Boolean(jobId),refetchInterval:3000});
  const generate=useMutation({mutationFn:()=>api.sectionResearchGenerate(reportId!,sectionId,{force:true,async:true}),onSuccess:d=>setJobId(d.job_id??"")});
  const validate=useMutation({mutationFn:()=>api.sectionResearchValidate(reportId!,sectionId)});
  useEffect(()=>{
    const s=job.data?.status;
    if(s==="completed"||s==="failed"||s==="cancelled"){
      setJobId("");
      void Promise.all([
        qc.invalidateQueries({queryKey:["section-research-current",reportId,sectionId]}),
        qc.invalidateQueries({queryKey:["section-research-runs",reportId,sectionId]})
      ]);
    }
  },[job.data?.status,qc,reportId,sectionId]);
  const selected=sections.find(s=>s.id===sectionId);
  return <>
    <div className="page-head"><div><div className="eyebrow">Section research</div><h1>Section Research</h1><p>Retrieve evidence for one manuscript section against its research contract.</p></div></div>
    <Context reportId={reportId}/>
    {!reportId?<section className="card pad" style={{marginTop:16}}><State title="No active report" description="Create a report and manuscript before running section research."/></section>:
    <>
      <section className="card pad" style={{marginTop:16}}>
        <div className="field"><label>Manuscript section</label><select className="input" value={sectionId} onChange={e=>setSectionId(e.target.value)} disabled={manuscript.isPending||!sections.length}>
          {sections.map(s=><option key={s.id} value={s.id}>{s.title} · {s.section_key}</option>)}
        </select></div>
        {!sections.length&&!manuscript.isPending&&<div className="notice" style={{marginTop:10}}>No manuscript sections are available for the current report.</div>}
        {selected&&<div className="grid grid-3" style={{marginTop:12}}><Metric label="Word budget" value={selected.word_budget}/><Metric label="Evidence target" value={Math.round(selected.evidence_coverage_target*100)+"%"}/><Metric label="Status" value={selected.status}/></div>}
        <button className="btn primary" style={{marginTop:12}} disabled={!sectionId||generate.isPending||Boolean(jobId)} onClick={()=>generate.mutate()}>{generate.isPending?"Queueing…":"Run section research"}</button>
        {jobId&&<div className="notice" style={{marginTop:10}}>Job: {job.data?.status??"queued"}</div>}
        {generate.isError&&<div className="notice error" style={{marginTop:10}}>{generate.error instanceof Error?generate.error.message:"Section research failed."}</div>}
      </section>
      {current.isError?<section className="card pad" style={{marginTop:16}}><State title="No completed section research" description="Run section research to retrieve evidence for this section."/></section>:
      current.data&&<>
        <section className="card pad" style={{marginTop:16}}><div className="row"><div><h3>Coverage</h3><div className="muted small">{current.data.run.primary_query}</div></div><span className="tag">{Math.round(current.data.run.coverage_score*100)}% · {current.data.run.coverage_state}</span></div>
          {current.data.coverage&&<div className="list" style={{marginTop:10}}>{current.data.coverage.per_requirement.map(item=><div className="list-item" key={item.requirement_key}><div className="row"><span className="title">{item.requirement_key}</span><span className="tag">{Math.round(item.coverage_score*100)}% · {item.status}</span></div><div className="muted small" style={{marginTop:4}}>{item.reason}</div></div>)}</div>}
          {current.data.coverage?.warnings?.length&&<div className="notice" style={{marginTop:10}}>Warnings: {current.data.coverage.warnings.join(" · ")}</div>}
          {current.data.run.warnings?.length&&<div className="notice" style={{marginTop:10}}>Run warnings: {current.data.run.warnings.map(String).join(" · ")}</div>}
          <button className="btn" style={{marginTop:10}} disabled={validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate research run"}</button>
          {validate.data&&<div className={"notice "+(validate.data.validation_status==="valid"?"success":"error")} style={{marginTop:10}}>Validation: {validate.data.validation_status}{validate.data.validation_errors.length?" · "+validate.data.validation_errors.join(", "):""}</div>}
        </section>
        <section className="card pad" style={{marginTop:16}}><div className="row"><h3>Selected evidence</h3><span className="tag">{current.data.evidence.length}</span></div>
          {current.data.evidence.length===0?<State title="No evidence selected" description="The current run did not persist evidence records for this section."/>:
          <div className="list" style={{marginTop:10}}>{current.data.evidence.map(e=><div className="list-item" key={e.id}><div className="row"><div className="title">{e.citation_label??("Evidence "+e.rank)}</div><span className="tag">{Math.round(e.final_score*100)}%</span></div><div className="meta">{e.evidence_role} · {e.retrieval_stage} · Source {e.source_id}</div><div className="muted small" style={{marginTop:5}}>{e.excerpt??"No excerpt stored."}</div><div className="muted tiny" style={{marginTop:5}}>{e.matched_requirement_keys.join(", ")||"No matched requirements"}</div></div>)}</div>}
        </section>
        <section className="card pad" style={{marginTop:16}}><div className="row"><h3>Run history</h3><span className="tag">{runs.data?.total??0}</span></div>
          {runs.data?.items.map(r=><div className="list-item" key={r.id}><div className="row"><span>{r.status}</span><span className="tag">{Math.round(r.coverage_score*100)}% · {r.coverage_state}</span></div><div className="meta">{new Date(r.created_at).toLocaleString()} · {r.primary_query}</div></div>)}
        </section>
      </>}
    </>}
  </>;
}
