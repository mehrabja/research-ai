"use client";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiErrorFromResponse } from "@/lib/api/errors";
import { useResearchContext } from "@/lib/research-context";
import { ResearchContextSwitcher } from "./ResearchContextSwitcher";
import { CommandPalette } from "@/components/CommandPalette";

type Notification = { id:string; title:string; body:string; kind:string; read_at:string|null; created_at:string };
type NotificationResponse = { items:Notification[]; unread:number; total:number };

async function readNotifications(): Promise<NotificationResponse> {
  const response=await fetch("/api/v1/notifications?limit=10",{credentials:"include",headers:{Accept:"application/json"},cache:"no-store"});
  if(!response.ok) throw await apiErrorFromResponse(response,"Unable to load notifications.");
  return response.json() as Promise<NotificationResponse>;
}
async function markRead(id:string):Promise<void>{
  const response=await fetch("/api/v1/notifications/"+id+"/read",{method:"POST",credentials:"include",headers:{Accept:"application/json"}});
  if(!response.ok) throw await apiErrorFromResponse(response,"Unable to mark notification as read.");
}
async function markAllRead():Promise<void>{
  const response=await fetch("/api/v1/notifications/read-all",{method:"POST",credentials:"include"});
  if(!response.ok) throw await apiErrorFromResponse(response,"Unable to mark notifications as read.");
}
function formatNotificationDate(value:string):string{const date=new Date(value);return Number.isNaN(date.getTime())?value:date.toLocaleString();}
function initials(email:string):string{const local=email.split("@")[0]??email;const clean=local.replace(/[^a-zA-Z0-9]/g,"");return clean.slice(0,2).toUpperCase()||"R";}

export function Topbar({onMenuClick}:{onMenuClick:()=>void}){
  const [open,setOpen]=useState(false);
  const [commandOpen,setCommandOpen]=useState(false);
  const queryClient=useQueryClient();
  const {user,project}=useResearchContext();
  const notificationsQuery=useQuery({queryKey:["notifications",10],queryFn:readNotifications,refetchInterval:30_000});
  useEffect(()=>{
    function onKeyDown(event:KeyboardEvent){
      if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==="k"){event.preventDefault();setCommandOpen(true);}
      if(event.key==="Escape") setOpen(false);
    }
    window.addEventListener("keydown",onKeyDown);
    return()=>window.removeEventListener("keydown",onKeyDown);
  },[]);
  const notifications=notificationsQuery.data??{items:[],unread:0,total:0};
  const notificationError=notificationsQuery.error instanceof Error?notificationsQuery.error.message:null;
  const markReadMutation=useMutation({mutationFn:markRead,onSuccess:()=>void queryClient.invalidateQueries({queryKey:["notifications"]})});
  const markAllReadMutation=useMutation({mutationFn:markAllRead,onSuccess:()=>void queryClient.invalidateQueries({queryKey:["notifications"]})});
  return <>
    <header className="topbar">
      <div className="topbar-left">
        <button className="btn ghost mobile-menu" type="button" aria-label="Open navigation" onClick={onMenuClick}>☰</button>
        <button className="topbar-search" type="button" onClick={()=>setCommandOpen(true)} aria-label="Open command palette"><span>Search or jump…</span><kbd>⌘K</kbd></button>
        <ResearchContextSwitcher />
      </div>
      <div className="topbar-right">
        {project&&<span className="current-project-tag" title={project.name}>{project.name}</span>}
        <div style={{position:"relative"}}>
          <button className="btn ghost" type="button" aria-label="Notifications" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>🔔{notifications.unread>0&&<span aria-label={notifications.unread+" unread notifications"} style={{marginLeft:6,fontSize:11,fontWeight:700}}>{notifications.unread}</span>}</button>
          {open&&<div className="card pad notification-popover" role="dialog" aria-label="Notifications">
            <div className="row"><div><h3>Notifications</h3><div className="muted small">{notifications.unread} unread</div></div>
              {notifications.unread>0&&<button className="btn ghost" type="button" disabled={markAllReadMutation.isPending} onClick={()=>markAllReadMutation.mutate()}>{markAllReadMutation.isPending?"Saving…":"Mark all read"}</button>}
            </div>
            {notificationError&&<p className="hint" role="alert" style={{color:"var(--danger)"}}>{notificationError}</p>}
            <div className="stack" style={{marginTop:12}}>
              {notifications.items.map(item=><button key={item.id} type="button" className="list-item" style={{textAlign:"left",border:0,background:item.read_at?"transparent":"rgba(159,169,255,.08)",cursor:item.read_at?"default":"pointer"}} disabled={Boolean(item.read_at)||markReadMutation.isPending} onClick={()=>markReadMutation.mutate(item.id)}>
                <div className="row"><strong>{item.title}</strong>{!item.read_at&&<span className="tag">Unread</span>}</div><div className="muted small" style={{marginTop:4}}>{item.body}</div><div className="muted tiny" style={{marginTop:6}}>{formatNotificationDate(item.created_at)}</div>
              </button>)}
              {notifications.items.length===0&&<div className="muted small">No notifications.</div>}
            </div>
          </div>}
        </div>
        <button type="button" className="user-chip" onClick={()=>{window.location.href="/settings";}} title={user.email}><span className="avatar">{initials(user.email)}</span><span className="user-chip-copy"><strong>{user.email}</strong><span>Account settings</span></span></button>
      </div>
    </header>
    <CommandPalette open={commandOpen} onClose={()=>setCommandOpen(false)} />
  </>;
}