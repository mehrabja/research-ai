export function progressPercent(completed:number,total:number):number {
  if (!Number.isFinite(completed) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.max(0,Math.min(100,Math.round((completed/total)*100)));
}
export function isTerminalJobStatus(status:string|undefined):boolean {
  return status==="completed" || status==="failed" || status==="cancelled";
}
export function isActiveRunStatus(status:string|undefined):boolean {
  return status==="queued" || status==="running" || status==="paused" || status==="awaiting_approval";
}
