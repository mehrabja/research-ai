"use client";
import { useWorkspace } from "@/components/app-shell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export default function JobsPage(){
  const {workspaceId}=useWorkspace();
  const qc=useQueryClient();
  const q=useQuery({
    queryKey:["jobs",workspaceId],
    queryFn:()=>api.jobs(),
    enabled:!!workspaceId
  });
  const retry=useMutation({
    mutationFn:(id:string)=>api.retryJob(id),
    onSuccess:()=>qc.invalidateQueries({queryKey:["jobs",workspaceId]})
  });

  return <div className="space-y-7">
    <header>
      <div className="kicker">Operations</div>
      <h1 className="text-3xl font-semibold mt-2">Jobs</h1>
      <p className="muted mt-2">Durable queue state, retries, leases, and terminal errors.</p>
    </header>
    <section className="card overflow-hidden">
      <div className="divide-y">
        {(q.data??[]).map(j=><div key={j.id} className="px-5 py-4 flex justify-between gap-4">
          <div>
            <div className="font-medium">{j.job_type}</div>
            <div className="muted text-xs mt-1 font-mono">{j.id}</div>
            {j.last_error_message&&<div className="text-xs mt-2" style={{color:"var(--danger)"}}>{j.last_error_message}</div>}
          </div>
          <div className="text-right">
            <div>{j.status}</div>
            <div className="muted text-xs mt-1">{j.attempt_count}/{j.max_attempts}</div>
            {(j.status==="failed"||j.status==="cancelled")&&<button className="btn btn-secondary text-xs mt-2" onClick={()=>retry.mutate(j.id)} disabled={retry.isPending}>Retry</button>}
          </div>
        </div>)}
        {q.isPending&&<div className="p-6 muted">Loading jobs…</div>}
        {!q.isPending&&!q.data?.length&&<div className="p-6 muted">No jobs for the authenticated user.</div>}
      </div>
    </section>
  </div>
}