"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { NAV_ITEMS } from "@/components/AppShell/nav-items";
import { useResearchContext } from "@/lib/research-context";

export function CommandPalette({open,onClose}:{open:boolean;onClose:()=>void}){
  const [query,setQuery]=useState("");
  const inputRef=useRef<HTMLInputElement|null>(null);
  const {contextHref,project,report}=useResearchContext();
  useEffect(()=>{
    if(!open)return;
    setQuery("");
    window.setTimeout(()=>inputRef.current?.focus(),0);
    function onKeyDown(event:KeyboardEvent){if(event.key==="Escape")onClose();}
    window.addEventListener("keydown",onKeyDown);
    return()=>window.removeEventListener("keydown",onKeyDown);
  },[onClose,open]);
  const commands=useMemo(()=>{
    const base=NAV_ITEMS.map(item=>({id:item.href,title:item.label,description:item.section,href:contextHref(item.href)}));
    const currentResearch={id:"current-research",title:project?"Open "+project.name:"Open current project",description:"Current research context",href:contextHref("/research")};
    const currentReport=report?[{id:"current-report",title:"Open current report",description:report.topic,href:contextHref("/manuscript")}]:[];
    return [currentResearch,...currentReport,...base];
  },[contextHref,project,report]);
  const normalized=query.trim().toLowerCase();
  const filtered=normalized?commands.filter(c=>[c.title,c.description].join(" ").toLowerCase().includes(normalized)):commands;
  if(!open)return null;
  return <div className="command-overlay">
    <button className="command-backdrop" type="button" aria-label="Close command palette" onClick={onClose}/>
    <section className="command-palette card" role="dialog" aria-modal="true" aria-labelledby="command-palette-title">
      <div className="command-head"><div><div className="eyebrow">Quick navigation</div><h2 id="command-palette-title">Command palette</h2></div><button className="btn ghost" type="button" onClick={onClose}>Esc</button></div>
      <input ref={inputRef} className="input command-input" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search views and current research…" aria-label="Search commands"/>
      <div className="command-list" role="listbox" aria-label="Commands">
        {filtered.map(c=><Link key={c.id} href={c.href} className="command-item" onClick={onClose}><span><strong>{c.title}</strong><span>{c.description}</span></span><span aria-hidden="true">↵</span></Link>)}
        {filtered.length===0&&<div className="empty command-empty">No matching commands.</div>}
      </div>
    </section>
  </div>;
}