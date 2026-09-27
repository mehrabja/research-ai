"use client";
import{useEffect,useState}from"react";
import{useMutation,useQuery,useQueryClient}from"@tanstack/react-query";
import{useWorkspace}from"@/components/app-shell";
import{api}from"@/lib/api/client";

const keys=[["job_completed","Job completions"],["member_invited","Membership activity"],["billing","Billing activity"],["research","Research activity"]] as const;

export default function NotificationsSettingsPage(){
 const{workspaceId}=useWorkspace();const qc=useQueryClient();const[preferences,setPreferences]=useState<Record<string,boolean>>({});
 const q=useQuery({queryKey:["notification-preferences"],queryFn:api.notificationPreferences});
 const n=useQuery({queryKey:["notifications",workspaceId],queryFn:()=>api.notifications(workspaceId!),enabled:!!workspaceId});
 useEffect(()=>{if(q.data?.preferences)setPreferences(q.data.preferences)},[q.data]);
 const save=useMutation({mutationFn:()=>api.updateNotificationPreferences(preferences),onSuccess:r=>{setPreferences(r.preferences);qc.invalidateQueries({queryKey:["notification-preferences"]})}});
 const read=useMutation({mutationFn:(id:string)=>api.readNotification(id),onSuccess:()=>qc.invalidateQueries({queryKey:["notifications",workspaceId]})});
 const all=useMutation({mutationFn:()=>api.readAllNotifications(workspaceId!),onSuccess:()=>qc.invalidateQueries({queryKey:["notifications",workspaceId]})});
 return <div className="space-y-7"><header><div className="kicker">Settings</div><h1 className="text-3xl font-semibold mt-2">Notifications</h1><p className="muted mt-2">Control event categories and review delivered workspace activity.</p></header>
 <section className="card p-5 space-y-4"><div><h2 className="font-semibold">Preferences</h2><p className="muted text-sm mt-1">Unset categories remain enabled by default.</p></div>{keys.map(([key,label])=><label key={key} className="flex items-center justify-between gap-4 py-2"><span>{label}</span><input type="checkbox" checked={preferences[key]!==false} onChange={e=>setPreferences(p=>({...p,[key]:e.target.checked}))}/></label>)}<button className="btn btn-primary" disabled={save.isPending} onClick={()=>save.mutate()}>Save preferences</button></section>
 <section className="card p-5 space-y-4"><div className="flex items-center justify-between"><div><h2 className="font-semibold">Inbox</h2><div className="text-2xl mt-1">{n.data?.unread??"—"} <span className="muted text-sm">unread</span></div></div><button className="btn btn-secondary" disabled={all.isPending||!n.data?.unread} onClick={()=>all.mutate()}>Mark all read</button></div><div className="divide-y" style={{borderColor:"var(--line)"}}>{(n.data?.items??[]).map(x=><div key={x.id} className="py-4 flex items-start justify-between gap-4"><div><div className="font-medium">{x.title}</div><div className="muted text-sm mt-1">{x.body}</div><div className="muted text-xs mt-2">{x.created_at}</div></div>{!x.read_at&&<button className="btn btn-secondary text-xs" onClick={()=>read.mutate(x.id)}>Mark read</button>}</div>)}</div></section></div>
}