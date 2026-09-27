"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export default function IntegrationsPage(){
  const q=useQuery({
    queryKey:["provider-matrix"],
    queryFn:()=>api.providerMatrix(),
  });
  return <div className="space-y-7">
    <header>
      <div className="kicker">Settings</div>
      <h1 className="text-3xl font-semibold mt-2">Integrations</h1>
      <p className="muted mt-2">Provider selection is server-side. This matrix exposes the active capability routing without exposing credentials.</p>
    </header>
    <section className="card overflow-hidden">
      <div className="divide-y">
        {(q.data?.capabilities??[]).map(item=><div key={item.capability} className="px-5 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div><div className="font-medium">{item.capability}</div><div className="muted text-xs mt-1">preferred: {item.configured_preferred||"not configured"}</div></div>
          <div className="flex flex-wrap gap-2">{item.available_providers.map(provider=><span key={provider} className="px-2.5 py-1 rounded-full text-xs border" style={{borderColor:"var(--line)"}}>{provider}</span>)}</div>
        </div>)}
        {q.isPending&&<div className="p-6 muted">Loading provider matrix…</div>}
        {q.isError&&<div className="p-6 text-sm" style={{color:"var(--danger)"}}>{q.error instanceof Error?q.error.message:"Unable to load providers."}</div>}
      </div>
    </section>
  </div>;
}