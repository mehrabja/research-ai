"use client";

import Link from"next/link";
import{use,useState}from"react";
import{useMutation,useQuery,useQueryClient}from"@tanstack/react-query";
import{api}from"@/lib/api/client";
import{useWorkspace}from"@/components/app-shell";

const LANGUAGES=[["en","English"],["fa","Persian"],["de","German"],["fr","French"]] as const;

export default function ProjectPage({params}:{params:Promise<{projectId:string}>}){
  const{projectId}=use(params);
  const{workspaceId}=useWorkspace();
  const qc=useQueryClient();
  const project=useQuery({queryKey:["project",projectId,workspaceId],queryFn:()=>api.project(projectId,workspaceId!),enabled:!!workspaceId});
  const reports=useQuery({queryKey:["project-reports",projectId,workspaceId],queryFn:()=>api.projectReports(projectId,workspaceId!),enabled:!!workspaceId});
  const[question,setQuestion]=useState("");
  const[topic,setTopic]=useState("");
  const[language,setLanguage]=useState<"en"|"fa"|"de"|"fr">("en");
  const rag=useMutation({mutationFn:()=>api.ragRetrieve(projectId,{query:question,mode:"hybrid",max_results:10})});
  const createReport=useMutation({
    mutationFn:()=>api.createReport(workspaceId!,{topic,output_language:language,project_id:projectId}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:["project-reports",projectId,workspaceId]});setTopic("")}
  });
  if(!workspaceId||project.isPending)return <div className="card p-6 muted">Loading project…</div>;
  if(project.error)return <div className="card p-6" style={{color:"var(--danger)"}}>Project unavailable: {project.error.message}</div>;
  return <div className="space-y-7">
    <div><Link href="/projects" className="muted text-sm">← Projects</Link><h1 className="text-3xl font-semibold mt-2">{project.data.name}</h1><p className="muted mt-2">{project.data.description||"No description."}</p></div>
    <div className="grid xl:grid-cols-2 gap-5">
      <section className="card p-5"><h2 className="font-semibold">Project context</h2><div className="grid sm:grid-cols-2 gap-4 mt-5 text-sm"><Field label="Domain" value={project.data.domain}/><Field label="Objective" value={project.data.research_objective}/><Field label="Scope" value={project.data.scope}/><Field label="Constraints" value={project.data.constraints}/></div></section>
      <section className="card p-5"><h2 className="font-semibold">Evidence retrieval</h2><p className="muted text-sm mt-1">Uses the existing project RAG endpoint.</p><div className="mt-4 flex gap-2"><input className="input" placeholder="Research question…" value={question} onChange={e=>setQuestion(e.target.value)}/><button className="btn btn-primary" disabled={!question||rag.isPending} onClick={()=>rag.mutate()}>{rag.isPending?"Searching…":"Retrieve"}</button></div>{rag.error&&<div className="text-sm mt-2" style={{color:"var(--danger)"}}>{rag.error.message}</div>}<div className="mt-4 space-y-3">{(rag.data?.results??[]).map(x=><div key={x.chunk_id??x.rank} className="rounded-xl border p-3" style={{borderColor:"var(--line)"}}><div className="flex justify-between text-xs muted"><span>Rank {x.rank}</span><span>{x.final_score.toFixed(3)}</span></div><div className="text-sm mt-2">{x.retrieval_reason.join(" · ")||x.retrieval_stage}</div><div className="text-xs muted mt-2">source {x.source_id??"—"} · chunk {x.chunk_id??"—"}</div></div>)}</div></section>
    </div>
    <section className="card p-5"><h2 className="font-semibold">Create report</h2><div className="mt-4 grid md:grid-cols-[1fr_180px_auto] gap-2"><input className="input" placeholder="Report topic" value={topic} onChange={e=>setTopic(e.target.value)}/><select className="input" aria-label="Output language" value={language} onChange={e=>setLanguage(e.target.value as typeof language)}>{LANGUAGES.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select><button className="btn btn-primary" disabled={!topic||createReport.isPending} onClick={()=>createReport.mutate()}>{createReport.isPending?"Creating…":"Create report"}</button></div>{createReport.error&&<div className="text-sm mt-2" style={{color:"var(--danger)"}}>{createReport.error.message}</div>}</section>
    <section className="card overflow-hidden"><div className="px-5 py-4 border-b" style={{borderColor:"var(--line)"}}>Reports</div><div className="divide-y">{(reports.data?.items??[]).map(x=><Link key={x.id} href={"/reports/"+x.id} className="block px-5 py-4"><div className="flex justify-between"><div><div className="font-medium">{x.topic}</div><div className="muted text-sm mt-1">{x.output_language}</div></div><span className="muted text-sm">{x.status}</span></div></Link>)}</div></section>
  </div>;
}
function Field({label,value}:{label:string;value:string|null}){return <div><div className="muted">{label}</div><div className="mt-1">{value||"—"}</div></div>}