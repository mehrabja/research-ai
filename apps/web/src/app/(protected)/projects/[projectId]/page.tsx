"use client";

import Link from "next/link";
import {use,useEffect,useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {useRouter,useSearchParams} from "next/navigation";
import {api} from "@/lib/api/client";
import {useWorkspace} from "@/components/app-shell";

const LANGUAGES=[
  ["en","English"],
  ["fa","Persian"],
  ["de","German"],
  ["fr","French"],
] as const;

export default function ProjectPage({params}:{params:Promise<{projectId:string}>}){
  const {projectId}=use(params);
  const {workspaceId}=useWorkspace();
  const router=useRouter();
  const qc=useQueryClient();

  const project=useQuery({
    queryKey:["project",projectId,workspaceId],
    queryFn:()=>api.project(projectId,workspaceId!),
    enabled:!!workspaceId,
  });
  const reports=useQuery({
    queryKey:["project-reports",projectId,workspaceId],
    queryFn:()=>api.projectReports(projectId,workspaceId!),
    enabled:!!workspaceId,
  });

  const searchParams=useSearchParams();
  const requestedReportId=searchParams.get("reportId");
  const reportId=reports.data?.items?.[0]?.id;
  const [selectedReportId,setSelectedReportId]=useState<string>("");
  const activeReportId=selectedReportId||reportId||"";
  const sources=useQuery({
    queryKey:["project-sources",activeReportId],
    queryFn:()=>api.sources(activeReportId),
    enabled:!!activeReportId,
  });

  const [editing,setEditing]=useState(false);
  const [name,setName]=useState("");
  const [domain,setDomain]=useState("");
  const [objective,setObjective]=useState("");
  const [description,setDescription]=useState("");
  const [scope,setScope]=useState("");
  const [constraints,setConstraints]=useState("");
  const [questions,setQuestions]=useState("");
  const [topic,setTopic]=useState("");
  const [language,setLanguage]=useState<"en"|"fa"|"de"|"fr">("en");

  useEffect(()=>{
    if(!project.data)return;
    setName(project.data.name);
    setDomain(project.data.domain??"");
    setObjective(project.data.research_objective??"");
    setDescription(project.data.description??"");
    setScope(project.data.scope??"");
    setConstraints(project.data.constraints??"");
    setQuestions((project.data.research_questions??[]).join("\n"));
  },[project.data]);

  useEffect(()=>{
    const validReportIds=reports.data?.items?.map(item=>item.id)??[];
    if(requestedReportId&&validReportIds.includes(requestedReportId)){
      setSelectedReportId(requestedReportId);
      return;
    }
    if(!selectedReportId&&reportId)setSelectedReportId(reportId);
  },[requestedReportId,reportId,reports.data,selectedReportId]);

  const update=useMutation({
    mutationFn:()=>api.updateProject(projectId,workspaceId!,{
      name:name.trim(),
      domain:domain.trim()||null,
      research_objective:objective.trim()||null,
      description:description.trim()||null,
      scope:scope.trim()||null,
      constraints:constraints.trim()||null,
      research_questions:questions.split("\n").map(x=>x.trim()).filter(Boolean),
    }),
    onSuccess:async()=>{
      await Promise.all([
        qc.invalidateQueries({queryKey:["project",projectId,workspaceId]}),
        qc.invalidateQueries({queryKey:["projects",workspaceId]}),
      ]);
      setEditing(false);
    },
  });

  const createReport=useMutation({
    mutationFn:()=>api.createReport(workspaceId!,{
      topic:topic.trim(),
      output_language:language,
      project_id:projectId,
    }),
    onSuccess:async report=>{
      await qc.invalidateQueries({queryKey:["project-reports",projectId,workspaceId]});
      setSelectedReportId(report.id);
      setTopic("");
      router.replace("/projects/"+projectId+"?setup=research&reportId="+report.id);
    },
  });

  const archive=useMutation({
    mutationFn:()=>api.archiveProject(projectId,workspaceId!),
    onSuccess:async()=>{
      await Promise.all([
        qc.invalidateQueries({queryKey:["project",projectId,workspaceId]}),
        qc.invalidateQueries({queryKey:["projects",workspaceId]}),
      ]);
      router.push("/projects");
    },
  });

  const activeReport=useMemo(
    ()=>reports.data?.items?.find(x=>x.id===activeReportId)??reports.data?.items?.[0],
    [reports.data,activeReportId],
  );
  const savedSources=sources.data?.items??[];
  const processedSources=savedSources.filter(x=>["full_text","structured_full_text"].includes(x.status));

  const contextReady=Boolean(project.data&&(project.data.name.trim()&&(project.data.research_objective?.trim()||project.data.domain?.trim()||project.data.description?.trim())));
  const reportReady=(reports.data?.items?.length??0)>0;
  const sourcesReady=savedSources.length>0;
  const researchReady=processedSources.length>0;
  const progress=[contextReady,reportReady,sourcesReady,researchReady].filter(Boolean).length;

  if(!workspaceId||project.isPending){
    return <div className="card p-6 muted">Loading project…</div>;
  }
  if(project.error){
    return <div className="card p-6" style={{color:"var(--danger)"}}>Project unavailable: {project.error.message}</div>;
  }

  return (
    <div className="space-y-7">
      <div>
        <Link href="/projects" className="muted text-sm">← Projects</Link>
        <div className="row" style={{marginTop:14,alignItems:"flex-start"}}>
          <div style={{minWidth:0}}>
            <div className="kicker">Project</div>
            <h1 className="text-3xl font-semibold mt-2" style={{overflowWrap:"anywhere"}}>{project.data.name}</h1>
            <p className="muted mt-2">{project.data.description||"No description yet."}</p>
          </div>
          <div className="actions">
            <span className={"tag"+(project.data.status==="active"?" primary":"")}>{project.data.status}</span>
            <button className="btn" onClick={()=>setEditing(x=>!x)}>{editing?"Close editor":"Edit project"}</button>
            {project.data.status==="active"&&<button
              className="btn"
              disabled={archive.isPending}
              onClick={()=>{if(window.confirm("Archive this project?"))archive.mutate();}}
            >{archive.isPending?"Archiving…":"Archive project"}</button>}
          </div>
        </div>
      </div>
      {archive.isError&&<div className="notice error" style={{marginTop:12}}>{archive.error instanceof Error?archive.error.message:"Project archive failed."}</div>}

      <section className="card p-5">
        <div className="row">
          <div>
            <h2 className="font-semibold">Project setup</h2>
            <p className="muted text-sm mt-1">Complete the project context, create a report, save sources and process at least one source for retrieval.</p>
          </div>
          <span className="tag primary">{progress} / 4 ready</span>
        </div>
        <div className="grid grid-4" style={{marginTop:16}}>
          <SetupStep index={1} title="Project defined" ready={contextReady} description="Name + research context"/>
          <SetupStep index={2} title="Report created" ready={reportReady} description="A report is inside the project"/>
          <SetupStep index={3} title="Sources saved" ready={sourcesReady} description="Research corpus exists"/>
          <SetupStep index={4} title="Research ready" ready={researchReady} description="At least one source is processed"/>
        </div>
        <div className="actions" style={{marginTop:16}}>
          {!reportReady&&<button className="btn primary" onClick={()=>document.getElementById("report-create")?.scrollIntoView({behavior:"smooth"})}>Create first report</button>}
          {reportReady&&<Link className="btn primary" href={"/research?projectId="+projectId+"&reportId="+activeReportId}>Continue to Research →</Link>}
          {reportReady&&<Link className="btn" href={"/sources?projectId="+projectId+"&reportId="+activeReportId}>Open Sources</Link>}
        </div>
      </section>

      {editing&&(
        <section className="card p-5">
          <div className="row">
            <div>
              <h2 className="font-semibold">Edit project context</h2>
              <p className="muted text-sm mt-1">Project context is reusable across the reports and research work underneath it.</p>
            </div>
          </div>
          <div className="grid grid-2" style={{marginTop:16}}>
            <FieldInput label="Project name" value={name} onChange={setName}/>
            <FieldInput label="Domain" value={domain} onChange={setDomain}/>
            <FieldArea label="Research objective" value={objective} onChange={setObjective}/>
            <FieldArea label="Description" value={description} onChange={setDescription}/>
            <FieldArea label="Scope" value={scope} onChange={setScope}/>
            <FieldArea label="Constraints" value={constraints} onChange={setConstraints}/>
            <div className="field" style={{gridColumn:"1 / -1"}}>
              <label>Research questions <span className="muted tiny">(one per line)</span></label>
              <textarea className="input textarea" value={questions} onChange={e=>setQuestions(e.target.value)} placeholder="One question per line…"/>
            </div>
          </div>
          <div className="actions" style={{marginTop:14,justifyContent:"flex-end"}}>
            <button className="btn" onClick={()=>setEditing(false)} disabled={update.isPending}>Cancel</button>
            <button className="btn primary" onClick={()=>update.mutate()} disabled={!name.trim()||update.isPending}>{update.isPending?"Saving…":"Save project"}</button>
          </div>
          {update.isError&&<div className="notice error" style={{marginTop:12}}>{update.error instanceof Error?update.error.message:"Project update failed."}</div>}
        </section>
      )}

      <section className="card p-5">
        <div className="grid grid-3">
          <div>
            <div className="muted text-xs">Project</div>
            <div className="mt-1 font-medium">Research container</div>
            <div className="muted text-sm mt-1">Owns shared context, scope and the research corpus.</div>
          </div>
          <div>
            <div className="muted text-xs">Report</div>
            <div className="mt-1 font-medium">One research deliverable</div>
            <div className="muted text-sm mt-1">Defines a topic, language and report-specific lifecycle.</div>
          </div>
          <div>
            <div className="muted text-xs">Workspace</div>
            <div className="mt-1 font-medium">Tenant boundary</div>
            <div className="muted text-sm mt-1">Controls membership, access, usage and billing around projects.</div>
          </div>
        </div>
      </section>

      <section className="card p-5" id="report-create">
        <div className="row" style={{alignItems:"flex-start"}}>
          <div>
            <h2 className="font-semibold">{reportReady?"Create another report":"Create the first report"}</h2>
            <p className="muted text-sm mt-1">Reports are inside this project. Create one before starting report-scoped discovery and source work.</p>
          </div>
        </div>
        <div className="mt-4 grid md:grid-cols-[1fr_180px_auto] gap-2">
          <input className="input" aria-label="Report topic" placeholder="Report topic" value={topic} onChange={e=>setTopic(e.target.value)}/>
          <select className="input" aria-label="Output language" value={language} onChange={e=>setLanguage(e.target.value as typeof language)}>
            {LANGUAGES.map(([code,label])=><option key={code} value={code}>{label}</option>)}
          </select>
          <button className="btn btn-primary" disabled={!topic.trim()||createReport.isPending} onClick={()=>createReport.mutate()}>{createReport.isPending?"Creating…":"Create report"}</button>
        </div>
        {createReport.isError&&<div className="notice error" style={{marginTop:12}}>{createReport.error instanceof Error?createReport.error.message:"Report creation failed."}</div>}
      </section>

      <section className="card p-5">
        <div className="row">
          <div>
            <h2 className="font-semibold">Reports in this project</h2>
            <p className="muted text-sm mt-1">Choose a report to continue the research workflow.</p>
          </div>
          <span className="tag">{reports.data?.items?.length??0} reports</span>
        </div>
        <div className="list" style={{marginTop:8}}>
          {(reports.data?.items??[]).map(r=>(
            <div className="list-item" key={r.id}>
              <div className="row" style={{alignItems:"flex-start"}}>
                <div style={{minWidth:0}}>
                  <div className="title" style={{overflowWrap:"anywhere"}}>{r.topic}</div>
                  <div className="meta">{r.output_language} · {r.status} · Updated {new Date(r.updated_at).toLocaleString()}</div>
                </div>
                <div className="actions">
                  <button className={"btn"+(r.id===activeReport?.id?" primary":"")} type="button" onClick={()=>{setSelectedReportId(r.id);router.replace("/projects/"+projectId+"?reportId="+r.id)}}>{r.id===activeReport?.id?"Selected":"Select report"}</button>
                  <Link className="btn" href={"/research?projectId="+projectId+"&reportId="+r.id}>Research</Link>
                  <Link className="btn" href={"/sources?projectId="+projectId+"&reportId="+r.id}>Sources</Link>
                </div>
              </div>
            </div>
          ))}
          {!reports.isPending&&!(reports.data?.items?.length)&&<div className="state"><h3>No reports yet</h3><p>Create the first report above to unlock report-scoped research discovery.</p></div>}
        </div>
      </section>

      {reportReady&&(
        <section className="card p-5">
          <div className="row">
            <div>
              <h2 className="font-semibold">Selected report readiness</h2>
              <p className="muted text-sm mt-1">{activeReport?.topic||"Report"} · {savedSources.length} saved sources · {processedSources.length} processed</p>
            </div>
            <div className="actions">
              <Link className="btn" href={"/research?projectId="+projectId+"&reportId="+activeReportId}>Research discovery</Link>
              <Link className="btn" href={"/literature?projectId="+projectId}>Literature</Link>
            </div>
          </div>
          {!sources.isPending&&savedSources.length===0&&<div className="notice" style={{marginTop:14}}>No sources are saved for this report yet. Start Research discovery to add the first source.</div>}
          {savedSources.length>0&&processedSources.length===0&&<div className="notice" style={{marginTop:14}}>Sources are saved, but none are processed yet. Open Sources and process at least one source to enable retrieval.</div>}
        </section>
      )}
    </div>
  );
}

function SetupStep({index,title,ready,description}:{index:number;title:string;ready:boolean;description:string}){
  return (
    <div className="notice" style={{borderColor:ready?"#BBF7D0":undefined,background:ready?"#F0FDF4":"#FBFCFD"}}>
      <div className="row">
        <span className={"tag"+(ready?" success":"")}>{ready?"✓":index}</span>
        <b>{title}</b>
      </div>
      <div className="muted tiny" style={{marginTop:6}}>{description}</div>
    </div>
  );
}

function FieldInput({label,value,onChange}:{label:string;value:string;onChange:(value:string)=>void}){
  return <div className="field"><label>{label}</label><input className="input" value={value} onChange={e=>onChange(e.target.value)}/></div>;
}

function FieldArea({label,value,onChange}:{label:string;value:string;onChange:(value:string)=>void}){
  return <div className="field"><label>{label}</label><textarea className="input textarea" style={{minHeight:120}} value={value} onChange={e=>onChange(e.target.value)}/></div>;
}
