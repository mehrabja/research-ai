"use client";

import Link from "next/link";
import {useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {useRouter} from "next/navigation";
import {api} from "@/lib/api/client";
import {useWorkspace} from "@/components/app-shell";

function splitLines(value:string):string[]{
  return value.split("\n").map(x=>x.trim()).filter(Boolean);
}

export default function Projects(){
  const {workspaceId}=useWorkspace();
  const router=useRouter();
  const qc=useQueryClient();
  const list=useQuery({
    queryKey:["projects",workspaceId],
    queryFn:()=>api.projects(workspaceId!),
    enabled:!!workspaceId,
  });

  const [step,setStep]=useState(1);
  const [name,setName]=useState("");
  const [domain,setDomain]=useState("");
  const [objective,setObjective]=useState("");
  const [description,setDescription]=useState("");
  const [scope,setScope]=useState("");
  const [constraints,setConstraints]=useState("");
  const [questions,setQuestions]=useState("");

  const create=useMutation({
    mutationFn:()=>api.createProject(workspaceId!,{
      name:name.trim(),
      domain:domain.trim()||undefined,
      research_objective:objective.trim()||undefined,
      description:description.trim()||undefined,
      scope:scope.trim()||undefined,
      constraints:constraints.trim()||undefined,
      research_questions:splitLines(questions),
    }),
    onSuccess:async project=>{
      await qc.invalidateQueries({queryKey:["projects",workspaceId]});
      setName("");
      setDomain("");
      setObjective("");
      setDescription("");
      setScope("");
      setConstraints("");
      setQuestions("");
      setStep(1);
      router.push("/projects/"+project.id+"?setup=report");
    },
  });

  if(!workspaceId){
    return <div className="card p-6 muted">Loading workspace…</div>;
  }

  const projects=list.data?.items??[];

  return (
    <div className="space-y-7">
      <div className="page-head" style={{marginBottom:0}}>
        <div>
          <div className="kicker">Workspace scoped</div>
          <h1 className="text-3xl font-semibold mt-2">Projects</h1>
          <p className="muted mt-2">A project is the durable container for one research effort. Reports, sources and evidence live inside it.</p>
        </div>
        <Link className="btn" href="/workspace">Workspace overview</Link>
      </div>

      <section className="card p-5">
        <div className="row">
          <div>
            <h2 className="font-semibold">Create a research project</h2>
            <p className="muted text-sm mt-1">Start with the research context, then continue directly into report setup.</p>
          </div>
          <span className="tag primary">Step {step} of 2</span>
        </div>

        <div className="grid grid-2" style={{marginTop:18}}>
          <div className={"notice"+(step===1?" primary":"")} style={{borderColor:step===1?"#C7D2FE":undefined}}>
            <b>1. Project context</b>
            <div className="muted tiny" style={{marginTop:4}}>Name, domain and research objective.</div>
          </div>
          <div className={"notice"+(step===2?" primary":"")} style={{borderColor:step===2?"#C7D2FE":undefined}}>
            <b>2. Scope & handoff</b>
            <div className="muted tiny" style={{marginTop:4}}>Scope, constraints and research questions.</div>
          </div>
        </div>

        {step===1 ? (
          <div className="grid grid-2" style={{marginTop:18}}>
            <div className="field">
              <label htmlFor="project-name">Project name</label>
              <input id="project-name" className="input" autoFocus value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. Climate adaptation literature review"/>
            </div>
            <div className="field">
              <label htmlFor="project-domain">Domain</label>
              <input id="project-domain" className="input" value={domain} onChange={e=>setDomain(e.target.value)} placeholder="e.g. Public health, NLP, Climate science"/>
            </div>
            <div className="field" style={{gridColumn:"1 / -1"}}>
              <label htmlFor="project-objective">Research objective</label>
              <textarea id="project-objective" className="input textarea" style={{minHeight:120}} value={objective} onChange={e=>setObjective(e.target.value)} placeholder="What decision, question or body of evidence is this project intended to address?"/>
            </div>
            <div className="field" style={{gridColumn:"1 / -1"}}>
              <label htmlFor="project-description">Description</label>
              <textarea id="project-description" className="input textarea" style={{minHeight:110}} value={description} onChange={e=>setDescription(e.target.value)} placeholder="Optional project context, audience or deliverable notes."/>
            </div>
          </div>
        ) : (
          <div className="grid grid-2" style={{marginTop:18}}>
            <div className="field">
              <label htmlFor="project-scope">Research scope</label>
              <textarea id="project-scope" className="input textarea" value={scope} onChange={e=>setScope(e.target.value)} placeholder="Population, geography, time range, methods or inclusion boundaries."/>
            </div>
            <div className="field">
              <label htmlFor="project-constraints">Constraints</label>
              <textarea id="project-constraints" className="input textarea" value={constraints} onChange={e=>setConstraints(e.target.value)} placeholder="Known limitations, exclusions, source restrictions or deadline constraints."/>
            </div>
            <div className="field" style={{gridColumn:"1 / -1"}}>
              <label htmlFor="project-research-questions">Research questions <span className="muted tiny">(one per line)</span></label>
              <textarea id="project-research-questions" className="input textarea" value={questions} onChange={e=>setQuestions(e.target.value)} placeholder={"What is already known?\nWhich findings are most consistent?\nWhere are the evidence gaps?"}/>
            </div>
            <div className="notice" style={{gridColumn:"1 / -1"}}>
              <b>Next step</b>
              <div className="muted tiny" style={{marginTop:4}}>After creation you will land on the project setup page, where the first report can be created and the Research → Sources flow is one click away.</div>
            </div>
          </div>
        )}

        <div className="actions" style={{marginTop:16,justifyContent:"flex-end"}}>
          {step===2&&<button className="btn" type="button" onClick={()=>setStep(1)} disabled={create.isPending}>Back</button>}
          {step===1&&<button className="btn primary" type="button" onClick={()=>setStep(2)} disabled={!name.trim()}>Continue</button>}
          {step===2&&<button className="btn primary" type="button" disabled={!name.trim()||create.isPending} onClick={()=>create.mutate()}>{create.isPending?"Creating…":"Create project"}</button>}
        </div>
        {create.isError&&<div className="notice error" style={{marginTop:12}}>{create.error instanceof Error?create.error.message:"Project creation failed."}</div>}
      </section>

      <section className="card overflow-hidden">
        <div className="px-5 py-4 border-b row" style={{borderColor:"var(--line)"}}>
          <div>
            <div className="font-semibold">Project inventory</div>
            <div className="muted text-xs mt-1">{projects.length} project{projects.length===1?"":"s"} in this workspace.</div>
          </div>
        </div>
        <div className="divide-y">
          {projects.map(p=>(
            <Link key={p.id} href={"/projects/"+p.id} className="block px-5 py-4" style={{transition:"background .12s"}}>
              <div className="row" style={{alignItems:"flex-start"}}>
                <div style={{minWidth:0}}>
                  <div className="font-medium" style={{overflowWrap:"anywhere"}}>{p.name}</div>
                  <div className="muted text-sm mt-1">{p.domain||"No domain"} · {p.report_count} report{p.report_count===1?"":"s"}</div>
                  <div className="muted text-xs mt-2">Updated {new Date(p.updated_at).toLocaleString()}</div>
                </div>
                <div className="actions" style={{justifyContent:"flex-end"}}>
                  <span className={"tag"+(p.status==="active"?" primary":"")}>{p.status}</span>
                  <span className="btn">Open project →</span>
                </div>
              </div>
            </Link>
          ))}
          {!list.isPending&&projects.length===0&&(
            <div className="p-8">
              <div className="state" style={{padding:"24px 10px"}}>
                <h3>No projects in this workspace</h3>
                <p>Create the first project above. The setup flow will then move you into the first research report.</p>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
