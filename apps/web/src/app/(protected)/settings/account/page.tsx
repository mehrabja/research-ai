"use client";
import{useQuery,useMutation,useQueryClient}from"@tanstack/react-query";
import{api}from"@/lib/api/client";
export default function AccountPage(){
 const qc=useQueryClient();const q=useQuery({queryKey:["sessions"],queryFn:api.sessions});
 const revoke=useMutation({mutationFn:(id:string)=>api.revokeSession(id),onSuccess:()=>qc.invalidateQueries({queryKey:["sessions"]})});
 return <div className="space-y-7"><header><div className="kicker">Account</div><h1 className="text-3xl font-semibold mt-2">Sessions</h1><p className="muted mt-2">Persistent refresh sessions are shown without exposing credential material.</p></header><section className="card overflow-hidden"><div className="divide-y">{(q.data??[]).map(s=><div key={s.id} className="px-5 py-4 flex items-center justify-between gap-4"><div><div className="font-medium">{s.id}</div><div className="muted text-xs mt-1">Created {s.created_at} · expires {s.expires_at}</div></div><button className="btn btn-secondary text-xs" onClick={()=>revoke.mutate(s.id)} disabled={revoke.isPending}>Revoke</button></div>)}{q.isPending&&<div className="p-6 muted">Loading sessions…</div>}{!q.isPending&&!q.data?.length&&<div className="p-6 muted">No active sessions returned.</div>}</div></section></div>;
}