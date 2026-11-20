"use client";

import {useEffect,useMemo,useState} from "react";
import {useSearchParams} from "next/navigation";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {useWorkspace} from "./app-shell";
import type {AcademicQACurrent,CitationCurrent,Classification} from "@/lib/api/generated";

function value(v:unknown,fallback="—"):string{
  if(typeof v==="string"&&v.trim())return v;
  if(typeof v==="number"||typeof v==="boolean")return String(v);
  return fallback;
}
function useQualityContext(){
  const ws=useWorkspace();
  const params=useSearchParams();
  const requestedProjectId=params.get("projectId");
  const requestedReportId=params.get("reportId");
  const projects=useQuery({queryKey:["quality-projects",ws.workspaceId],queryFn:()=>api.projects(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const projectId=useMemo(()=>requestedProjectId&&projects.data?.items.some(p=>p.id===requestedProjectId)?requestedProjectId:projects.data?.items[0]?.id,[projects.data,requestedProjectId]);
  const reports=useQuery({queryKey:["quality-reports",projectId],queryFn:()=>api.projectReports(projectId!,ws.workspaceId!),enabled:Boolean(projectId&&ws.workspaceId)});
  const reportId=useMemo(()=>requestedReportId&&reports.data?.items.some(r=>r.id===requestedReportId)?requestedReportId:reports.data?.items[0]?.id,[reports.data,requestedReportId]);
  return {projectId,reportId};
}
function Header({title,description}:{title:string;description:string}){return <div className="page-head"><div><div className="eyebrow">Quality gate</div><h1>{title}</h1><p>{description}</p></div></div>;}
function Context({projectId,reportId}:{projectId?:string;reportId?:string}){return <div className="card pad" style={{marginTop:16}}><div className="row"><div><div className="kicker">Backend context</div><div className="strong">Selected research context</div></div><span className="tag">Project {value(projectId)} · Report {value(reportId)}</span></div><div className="muted tiny" style={{marginTop:8}}>Results and mutations use persisted backend records for the selected context.</div></div>;}
function State({title,description,error=false}:{title:string;description:string;error?:boolean}){return <div className={"state"+(error?" error":"")}><h3>{title}</h3><p>{description}</p></div>;}
function Metric({label,value:v}:{label:string;value:unknown}){return <div className="card metric"><div className="label">{label}</div><div className="value">{value(v)}</div></div>;}

export function CitationsScreen(){
  const {reportId}=useQualityContext();
  const qc=useQueryClient();
  const manuscript=useQuery({queryKey:["citation-manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId),retry:false});
  const current=useQuery<CitationCurrent>({queryKey:["citation-current",reportId],queryFn:()=>api.citations(reportId!),enabled:Boolean(reportId),retry:false});
  const history=useQuery({queryKey:["citation-history",reportId],queryFn:()=>api.citationsHistory(reportId!),enabled:Boolean(reportId)});
  const [style,setStyle]=useState<"author_year"|"numeric">("author_year");
  const bibliography=useQuery({queryKey:["bibliography",reportId,style],queryFn:()=>api.citationsBibliography(reportId!,style),enabled:Boolean(reportId&&current.isSuccess),retry:false});
  const [jobId,setJobId]=useState("");
  const job=useQuery({queryKey:["citation-job",jobId],queryFn:()=>api.job(jobId),enabled:Boolean(jobId),refetchInterval:3000});
  const generate=useMutation({mutationFn:()=>api.citationsGenerate(reportId!,{manuscript_version_id:manuscript.data!.version.id,citation_style:style,force:true,async:true}),onSuccess:d=>setJobId(d.job_id??"")});
  const validate=useMutation({mutationFn:()=>api.citationsValidate(reportId!)});
  useEffect(()=>{const s=job.data?.status;if(s==="completed"||s==="failed"||s==="cancelled"){setJobId("");void Promise.all([qc.invalidateQueries({queryKey:["citation-current",reportId]}),qc.invalidateQueries({queryKey:["citation-history",reportId]}),qc.invalidateQueries({queryKey:["bibliography",reportId,style]})]);}},[job.data?.status,qc,reportId,style]);
  return <><Header title="Citations" description="Generate, inspect and validate persisted citation runs and bibliography."/><Context reportId={reportId}/>
  {!reportId?<section className="card pad" style={{marginTop:16}}><State title="No active report" description="Create a report before running the citation engine."/></section>:<div className="grid grid-2" style={{marginTop:16}}>
    <section className="card pad"><div className="row"><div><h3>Citation engine</h3><div className="muted small">Uses the current persisted manuscript version.</div></div>{current.data&&<span className="tag">{current.data.run.status}</span>}</div>
      <div className="grid grid-2" style={{marginTop:12}}><div className="field"><label>Citation style</label><select className="input" value={style} onChange={e=>{const v=e.target.value;if(v==="author_year"||v==="numeric")setStyle(v);}}><option value="author_year">Author-year</option><option value="numeric">Numeric</option></select></div><div className="field"><label>Manuscript version</label><input className="input" readOnly value={manuscript.data?.version.version?"v"+manuscript.data.version.version:"Loading…"}/></div></div>
      <button className="btn primary" style={{marginTop:12}} disabled={!manuscript.data?.version.id||generate.isPending||Boolean(jobId)} onClick={()=>generate.mutate()}>{generate.isPending?"Queueing…":"Generate citations"}</button>
      {jobId&&<div className="notice" style={{marginTop:10}}>Citation job: {job.data?.status??"queued"}</div>}
      {generate.isError&&<div className="notice error" style={{marginTop:10}}>{generate.error instanceof Error?generate.error.message:"Citation generation failed."}</div>}
      {current.data&&<div className="grid grid-4" style={{marginTop:14}}><Metric label="Claims" value={current.data.run.claim_count}/><Metric label="Citations" value={current.data.run.citation_count}/><Metric label="Unsupported" value={current.data.run.unsupported_count}/><Metric label="Coverage" value={Math.round(current.data.run.coverage_score*100)+"%"}/></div>}
      {current.data&&<button className="btn" style={{marginTop:10}} disabled={validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate run"}</button>}
      {validate.data&&<div className={"notice "+(validate.data.validation_status==="valid"?"success":"error")} style={{marginTop:10}}>Validation: {validate.data.validation_status}{validate.data.validation_errors.length?" · "+validate.data.validation_errors.join(", "):""}</div>}
    </section>
    <section className="card pad"><div className="row"><div><h3>Current claims</h3><div className="muted small">Claims persisted by the citation engine.</div></div><span className="tag">{current.data?.claims.length??0}</span></div>
      {current.isPending?<State title="Loading current run" description="Reading citation results."/>:current.isError?<State title="No completed citation run" description="Generate a run to populate claims and bibliography."/>:<div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Claim</th><th>Type</th><th>Status</th></tr></thead><tbody>{current.data?.claims.map(c=><tr key={c.id}><td style={{whiteSpace:"normal",overflowWrap:"anywhere"}}>{c.claim_text}</td><td>{c.claim_type}</td><td>{c.status}</td></tr>)}</tbody></table></div>}
    </section>
  </div>}
  {reportId&&current.data&&<><section className="card pad" style={{marginTop:16}}><div className="row"><div><h3>Bibliography</h3><div className="muted small">Rendered from identities cited by the current run.</div></div><span className="tag">{bibliography.data?.entries.length??0} entries</span></div>{bibliography.isPending?<State title="Building bibliography" description="Loading rendered references."/>:bibliography.isError?<State title="Bibliography unavailable" description={bibliography.error instanceof Error?bibliography.error.message:"Bibliography could not be loaded."} error/>:<div className="list" style={{marginTop:10}}>{bibliography.data?.entries.map(e=><div className="list-item" key={e.citation_id}><div className="title">{e.label}</div><div className="muted small" style={{marginTop:4}}>{e.rendered}</div></div>)}</div>}</section>
  <section className="card pad" style={{marginTop:16}}><div className="row"><h3>Run history</h3><span className="tag">{history.data?.total??0}</span></div>{history.data?.items.map(r=><div className="list-item" key={r.id}><div className="row"><span>{r.status}</span><span className="tag">{Math.round(r.coverage_score*100)}% coverage</span></div><div className="meta">{r.claim_count} claims · {r.citation_count} citations · {new Date(r.created_at).toLocaleString()}</div></div>)}</section></>}</>;
}

export function AcademicQAScreen(){
  const {reportId}=useQualityContext();
  const qc=useQueryClient();
  const manuscript=useQuery({queryKey:["qa-manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId),retry:false});
  const current=useQuery<AcademicQACurrent>({queryKey:["qa-current",reportId],queryFn:()=>api.qa(reportId!),enabled:Boolean(reportId),retry:false});
  const runs=useQuery({queryKey:["qa-runs",reportId],queryFn:()=>api.qaRuns(reportId!),enabled:Boolean(reportId)});
  const findings=useQuery({queryKey:["qa-findings",reportId],queryFn:()=>api.qaFindings(reportId!),enabled:Boolean(reportId&&current.isSuccess),retry:false});
  const [jobId,setJobId]=useState("");
  const job=useQuery({queryKey:["qa-job",jobId],queryFn:()=>api.job(jobId),enabled:Boolean(jobId),refetchInterval:3000});
  const generate=useMutation({mutationFn:()=>api.qaGenerate(reportId!,{manuscript_version_id:manuscript.data!.version.id,force:true,async:true}),onSuccess:d=>setJobId(d.job_id??"")});
  const validate=useMutation({mutationFn:()=>api.qaValidate(reportId!)});
  useEffect(()=>{const s=job.data?.status;if(s==="completed"||s==="failed"||s==="cancelled"){setJobId("");void Promise.all([qc.invalidateQueries({queryKey:["qa-current",reportId]}),qc.invalidateQueries({queryKey:["qa-runs",reportId]}),qc.invalidateQueries({queryKey:["qa-findings",reportId]})]);}},[job.data?.status,qc,reportId]);
  return <><Header title="Academic QA" description="Run the persisted academic quality gate and inspect actionable findings."/><Context reportId={reportId}/>
  {!reportId?<section className="card pad" style={{marginTop:16}}><State title="No active report" description="Create a report before running academic QA."/></section>:<div className="grid grid-2" style={{marginTop:16}}>
    <section className="card pad"><div className="row"><div><h3>Quality gate</h3><div className="muted small">Runs against the selected manuscript version.</div></div>{current.data&&<span className={"tag "+(current.data.run.gate==="pass"?"success":"")}>{current.data.run.gate??current.data.run.status}</span>}</div>
      <div className="field" style={{marginTop:12}}><label>Manuscript version</label><input className="input" readOnly value={manuscript.data?.version.version?"v"+manuscript.data.version.version:"Loading…"}/></div>
      <button className="btn primary" style={{marginTop:12}} disabled={!manuscript.data?.version.id||generate.isPending||Boolean(jobId)} onClick={()=>generate.mutate()}>{generate.isPending?"Queueing…":"Run academic QA"}</button>
      {jobId&&<div className="notice" style={{marginTop:10}}>QA job: {job.data?.status??"queued"}</div>}
      {generate.isError&&<div className="notice error" style={{marginTop:10}}>{generate.error instanceof Error?generate.error.message:"Academic QA failed."}</div>}
      {current.data&&<div className="grid grid-4" style={{marginTop:14}}><Metric label="Findings" value={current.data.run.finding_count}/><Metric label="Blocking" value={current.data.run.blocking_count}/><Metric label="Warnings" value={current.data.run.warning_count}/><Metric label="Info" value={current.data.run.info_count}/></div>}
      {current.data&&<button className="btn" style={{marginTop:10}} disabled={validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate QA run"}</button>}
      {validate.data&&<div className={"notice "+(validate.data.validation_status==="valid"?"success":"error")} style={{marginTop:10}}>Validation: {validate.data.validation_status}{validate.data.gate?" · gate "+validate.data.gate:""}</div>}
    </section>
    <section className="card pad"><div className="row"><div><h3>Findings</h3><div className="muted small">Persisted rule findings from the current QA run.</div></div><span className="tag">{findings.data?.total??0}</span></div>{findings.isPending?<State title="Loading findings" description="Reading academic QA findings."/>:findings.isError?<State title="No completed QA findings" description="Run Academic QA first."/>:findings.data?.items.map(f=><div className="list-item" key={f.id}><div className="row"><div><div className="title">{f.title}</div><div className="meta">{f.category} · {f.severity} · {f.rule_id}</div></div><span className="tag">{f.status}</span></div><div className="muted small" style={{marginTop:5}}>{f.message}</div></div>)}</section>
  </div>}
  {reportId&&<section className="card pad" style={{marginTop:16}}><div className="row"><h3>QA history</h3><span className="tag">{runs.data?.total??0}</span></div>{runs.data?.items.map(r=><div className="list-item" key={r.id}><div className="row"><span>{r.status}</span><span className="tag">{r.finding_count} findings · {r.blocking_count} blocking</span></div><div className="meta">{r.gate??"No gate"} · {new Date(r.created_at).toLocaleString()}</div></div>)}</section>}</>;
}

export function ClassificationScreen(){
  const {projectId}=useQualityContext();
  const qc=useQueryClient();
  const current=useQuery({queryKey:["classification",projectId],queryFn:()=>api.classification(projectId!),enabled:Boolean(projectId),retry:false});
  const evidence=useQuery({queryKey:["classification-evidence",projectId],queryFn:()=>api.classificationEvidence(projectId!),enabled:Boolean(projectId),retry:false});
  const history=useQuery({queryKey:["classification-history",projectId],queryFn:()=>api.classificationHistory(projectId!),enabled:Boolean(projectId)});
  const explanation=useQuery({queryKey:["classification-explanation",projectId],queryFn:()=>api.classificationExplanation(projectId!),enabled:Boolean(projectId),retry:false});
  const recompute=useMutation({mutationFn:()=>api.classificationRecompute(projectId!),onSuccess:()=>void Promise.all([qc.invalidateQueries({queryKey:["classification",projectId]}),qc.invalidateQueries({queryKey:["classification-evidence",projectId]}),qc.invalidateQueries({queryKey:["classification-history",projectId]}),qc.invalidateQueries({queryKey:["classification-explanation",projectId]})])});
  const [domain,setDomain]=useState("");const [paperType,setPaperType]=useState("");const [design,setDesign]=useState("");
  useEffect(()=>{setDomain(current.data?.domain.code??"");setPaperType(current.data?.paper_type.code??"");setDesign(current.data?.research_design.code??"");},[current.data?.id,current.data?.updated_at]);
  const override=useMutation({mutationFn:()=>api.classificationOverride(projectId!,{domain_code:domain.trim()||null,paper_type_code:paperType.trim()||null,research_design_code:design.trim()||null}),onSuccess:()=>{void qc.invalidateQueries({queryKey:["classification",projectId]});void qc.invalidateQueries({queryKey:["classification-history",projectId]});}});
  return <><Header title="Classification" description="Inspect research taxonomy classification, evidence and immutable history."/><Context projectId={projectId}/>
  {!projectId?<section className="card pad" style={{marginTop:16}}><State title="No active project" description="Create a project before computing classification."/></section>:<><div className="grid grid-3" style={{marginTop:16}}>
    <Dimension title="Domain" data={current.data?.domain}/><Dimension title="Paper type" data={current.data?.paper_type}/><Dimension title="Research design" data={current.data?.research_design}/>
  </div>
  <section className="card pad" style={{marginTop:16}}><div className="row"><div><h3>Controls</h3><div className="muted small">Recompute from project context or explicitly override the classifier result.</div></div><span className={"tag "+(current.data?.needs_review?"":"success")}>{current.data?.needs_review?"Needs review":current.data?.status??"—"}</span></div>
    <button className="btn primary" style={{marginTop:12}} disabled={recompute.isPending} onClick={()=>recompute.mutate()}>{recompute.isPending?"Recomputing…":"Recompute classification"}</button>
    <div className="grid grid-3" style={{marginTop:12}}><div className="field"><label>Domain code</label><input className="input" value={domain} onChange={e=>setDomain(e.target.value)}/></div><div className="field"><label>Paper type code</label><input className="input" value={paperType} onChange={e=>setPaperType(e.target.value)}/></div><div className="field"><label>Research design code</label><input className="input" value={design} onChange={e=>setDesign(e.target.value)}/></div></div>
    <button className="btn" style={{marginTop:10}} disabled={override.isPending} onClick={()=>override.mutate()}>{override.isPending?"Saving…":"Save explicit override"}</button>
    {recompute.isError&&<div className="notice error" style={{marginTop:10}}>{recompute.error instanceof Error?recompute.error.message:"Classification recompute failed."}</div>}
    {override.isError&&<div className="notice error" style={{marginTop:10}}>{override.error instanceof Error?override.error.message:"Classification override failed."}</div>}
  </section>
  <div className="grid grid-2" style={{marginTop:16}}>
    <section className="card pad"><div className="row"><div><h3>Evidence signals</h3><div className="muted small">Signals used by the classifier and their weights.</div></div><span className="tag">{evidence.data?.total??0}</span></div>{evidence.data?.items.map(e=><div className="list-item" key={e.id}><div className="row"><span className="title">{e.target}</span><span className="tag">{Math.round(e.weight*100)}%</span></div><div className="meta">{e.signal_type} · {e.target_code??"no target code"}</div><div className="muted tiny" style={{marginTop:4}}>{e.matched_text}</div></div>)}</section>
    <section className="card pad"><h3>Latest explanation</h3>{explanation.data?.explanation?<pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11,marginTop:10}}>{JSON.stringify(explanation.data.explanation,null,2)}</pre>:<State title="No explanation yet" description="Run classification to create an explanation."/>}</section>
  </div>
  <section className="card pad" style={{marginTop:16}}><div className="row"><h3>History</h3><span className="tag">{history.data?.total??0}</span></div>{history.data?.items.map(r=><div className="list-item" key={r.id}><div className="row"><span>{r.status}</span><span className="tag">{r.domain_code??"—"} / {r.paper_type_code??"—"} / {r.research_design_code??"—"}</span></div><div className="meta">{new Date(r.created_at).toLocaleString()} · {r.classifier_version}</div></div>)}</section>
  </>}</>;
}
function Dimension({title,data}:{title:string;data:Classification["domain"]|undefined}){
  return <section className="card pad"><div className="kicker">{title}</div><h3 style={{marginTop:5}}>{value(data?.code)}</h3><div className="meta">{data?.method??"—"} · {data?.source??"—"} · {data?.confidence===null||data?.confidence===undefined?"—":Math.round(data.confidence*100)+"%"}</div><div className="muted small" style={{marginTop:8}}>{data?.reason??"No reason recorded."}</div>{data?.alternatives?.length?<div className="list" style={{marginTop:10}}>{data.alternatives.slice(0,4).map(a=><div className="list-item" key={a.code??a.name??String(a.confidence)}>{a.code??a.name??"Alternative"} · {a.confidence===null||a.confidence===undefined?"—":Math.round(a.confidence*100)+"%"}</div>)}</div>:null}</section>;
}
