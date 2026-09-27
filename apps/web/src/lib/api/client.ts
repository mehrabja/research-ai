import type{Citation,Invitation,Manuscript,Member,Plan,Project,ProjectList,QA,RAGResponse,Report,Source,SourceCandidate,Usage,User,Workspace}from"./generated";
export class ApiError extends Error{
  status:number;
  code:string;
  requestId:string|null;
  details:unknown;
  constructor(message:string,status:number,code="API_ERROR",requestId:string|null=null,details?:unknown){
    super(message);this.name="ApiError";this.status=status;this.code=code;this.requestId=requestId;this.details=details;
  }
}
async function request<T>(path:string,init?:RequestInit):Promise<T>{
  const res=await fetch("/api/backend/"+path.replace(/^\//,""),{
    ...init,
    headers:{...(init?.body?{"content-type":"application/json"}:{}),...(init?.headers??{})},
    cache:"no-store"
  });
  const body=await res.json().catch(()=>null);
  if(!res.ok){
    const error=body?.error??body;
    const message=error?.message??body?.detail??body?.message??("Request failed ("+res.status+")");
    throw new ApiError(
      typeof message==="string"?message:JSON.stringify(message),
      res.status,
      typeof error?.code==="string"?error.code:"API_ERROR",
      typeof error?.request_id==="string"?error.request_id:(res.headers.get("x-request-id")??null),
      error?.details??error?.extra
    );
  }
  return body as T;
}
export const api={
me:()=>request<User>("auth/me"),
sessions:()=>request<Array<{id:string;created_at:string;expires_at:string;last_used_at:string|null}>>("auth/sessions"),
revokeSession:(id:string)=>request<object>("auth/sessions/"+id,{method:"DELETE"}),
workspaces:()=>request<{items:Workspace[];total:number}>("workspaces"),createWorkspace:(name:string)=>request<Workspace>("workspaces",{method:"POST",body:JSON.stringify({name})}),
projects:(w:string)=>request<ProjectList>("projects?workspace_id="+encodeURIComponent(w)),project:(p:string,w:string)=>request<Project>("projects/"+p+"?workspace_id="+encodeURIComponent(w)),createProject:(w:string,b:object)=>request<Project>("projects?workspace_id="+encodeURIComponent(w),{method:"POST",body:JSON.stringify(b)}),
projectReports:(p:string,w:string)=>request<{items:Array<{id:string;topic:string;status:string;output_language:string;updated_at:string}>;total:number}>("projects/"+p+"/reports?workspace_id="+encodeURIComponent(w)),reports:(w:string)=>request<Report[]>("reports?workspace_id="+encodeURIComponent(w)),createReport:(w:string,b:object)=>request<Report>("reports?workspace_id="+encodeURIComponent(w),{method:"POST",body:JSON.stringify(b)}),report:(r:string)=>request<Report>("reports/"+r),
sources:(r:string)=>request<{items:Source[]}>("reports/"+r+"/sources"),searchSources:(r:string,q:string)=>request<{query:string;limit:number;candidates:SourceCandidate[]} >("reports/"+r+"/sources/search?q="+encodeURIComponent(q)+"&limit=8"),createSource:(r:string,c:SourceCandidate)=>request<Source>("reports/"+r+"/sources",{method:"POST",body:JSON.stringify(c)}),
ragRetrieve:(p:string,b:object)=>request<RAGResponse>("projects/"+p+"/rag/retrieve",{method:"POST",body:JSON.stringify(b)}),manuscript:(r:string)=>request<Manuscript>("reports/"+r+"/manuscript"),citations:(r:string)=>request<Citation>("reports/"+r+"/citations/current"),qa:(r:string)=>request<QA>("reports/"+r+"/academic-qa/current"),
members:(w:string)=>request<{items:Member[];total:number}>("workspaces/"+w+"/members"),changeMemberRole:(w:string,u:string,role:string)=>request<Member>("workspaces/"+w+"/members/"+u,{method:"PATCH",body:JSON.stringify({role})}),removeMember:(w:string,u:string)=>request<null>("workspaces/"+w+"/members/"+u,{method:"DELETE"}),invitations:(w:string)=>request<{items:Invitation[];total:number}>("workspaces/"+w+"/members/invitations"),invite:(w:string,b:object)=>request<{invitation:Invitation;token:string}>("workspaces/"+w+"/members/invitations",{method:"POST",body:JSON.stringify(b)}),revokeInvitation:(w:string,i:string)=>request<null>("workspaces/"+w+"/members/invitations/"+i,{method:"DELETE"}),transferOwnership:(w:string,u:string)=>request<Workspace>("workspaces/"+w+"/transfer-ownership",{method:"POST",body:JSON.stringify({target_user_id:u})}),usage:(w:string)=>request<Usage>("workspaces/"+w+"/usage"),plan:(w:string)=>request<Plan>("workspaces/"+w+"/plan"),
subscription:(w:string)=>request<{subscription:Record<string,unknown>}>("billing/workspaces/"+w+"/subscription"),
checkout:(w:string,plan_code:string)=>request<{session_id:string;checkout_url:string|null}>("billing/workspaces/"+w+"/checkout",{method:"POST",body:JSON.stringify({plan_code})}),
changePlan:(w:string,plan_code:string)=>request<{status:string;subscription_id:string;cancel_at_period_end:boolean}>("billing/workspaces/"+w+"/plan",{method:"POST",body:JSON.stringify({plan_code})}),
cancelSubscription:(w:string)=>request<object>("billing/workspaces/"+w+"/cancel",{method:"POST"}),
resumeSubscription:(w:string)=>request<object>("billing/workspaces/"+w+"/resume",{method:"POST"}),
notifications:(w:string)=>request<{items:Array<{id:string;kind:string;title:string;body:string;read_at:string|null;created_at:string}>;total:number;unread:number}>("notifications?workspace_id="+encodeURIComponent(w)),
readNotification:(id:string)=>request<object>("notifications/"+id+"/read",{method:"POST"}),
readAllNotifications:(w:string)=>request<null>("notifications/read-all?workspace_id="+encodeURIComponent(w),{method:"POST"}),
notificationPreferences:()=>request<{preferences:Record<string,boolean>}>("notifications/preferences"),
updateNotificationPreferences:(preferences:Record<string,boolean>)=>request<{preferences:Record<string,boolean>}>("notifications/preferences",{method:"PATCH",body:JSON.stringify({preferences})}),
createAPIToken:(b:{name:string;expires_at?:string|null})=>request<{id:string;name:string;token:string;token_prefix:string;expires_at:string|null}>("auth/api-tokens",{method:"POST",body:JSON.stringify(b)}),
apiTokens:()=>request<Array<{id:string;name:string;token_prefix:string;last_used_at:string|null;expires_at:string|null;revoked_at:string|null;created_at:string}>>("auth/api-tokens"),
revokeAPIToken:(id:string)=>request<null>("auth/api-tokens/"+id,{method:"DELETE"}),
mfaStatus:()=>request<{enabled:boolean;recovery_codes_remaining:number}>("auth/mfa"),
mfaSetup:()=>request<{secret:string;provisioning_uri:string;recovery_codes:string[]}>("auth/mfa/setup",{method:"POST"}),
mfaEnable:(code:string)=>request<{enabled:boolean;recovery_codes_remaining:number}>("auth/mfa/enable",{method:"POST",body:JSON.stringify({code})}),
mfaDisable:(code:string)=>request<{enabled:boolean;recovery_codes_remaining:number}>("auth/mfa/disable",{method:"POST",body:JSON.stringify({code})}),
search:(w:string,q:string)=>request<{query:string;items:Array<{id:string;resource_type:string;title:string;snippet:string|null;updated_at:string}>;total:number}>("search?workspace_id="+encodeURIComponent(w)+"&q="+encodeURIComponent(q)),
evidenceMatrix:(r:string)=>request<object>("reports/"+r+"/evidence/matrix"),
graphExport:(p:string)=>request<object>("projects/"+p+"/knowledge-graph/export"),
savePlanRevision:(p:string,b:object)=>request<object>("projects/"+p+"/research-plan",{method:"PATCH",body:JSON.stringify(b)}),
restorePlanVersion:(p:string,v:number)=>request<object>("projects/"+p+"/research-plan/restore",{method:"POST",body:JSON.stringify({target_version:v})}),
manuscriptDraft:(r:string)=>request<object>("reports/"+r+"/manuscript/draft"),
saveManuscriptDraft:(r:string,b:object)=>request<object>("reports/"+r+"/manuscript/draft",{method:"PUT",body:JSON.stringify(b)}),
commitManuscriptDraft:(r:string,b:object)=>request<object>("reports/"+r+"/manuscript/draft/commit",{method:"POST",body:JSON.stringify(b)}),
providerMatrix:()=>request<{capabilities:Array<{capability:string;configured_preferred:string;available_providers:string[]}>}>("providers/matrix"),
folders:(p:string)=>request<{items:Array<{id:string;project_id:string;parent_id:string|null;name:string;created_at:string;updated_at:string}>;total:number}>("projects/"+p+"/folders"),
createFolder:(p:string,b:{name:string;parent_id?:string|null})=>request<object>("projects/"+p+"/folders",{method:"POST",body:JSON.stringify(b)}),
moveFile:(id:string,folder_id:string|null)=>request<object>("files/"+id+"/move"+(folder_id?"?folder_id="+encodeURIComponent(folder_id):""),{method:"POST"}),
jobs:()=>request<Array<{id:string;job_type:string;status:string;attempt_count:number;max_attempts:number;created_at:string;last_error_message:string|null}>>("jobs"),
retryJob:(id:string)=>request<object>("jobs/"+id+"/retry",{method:"POST"}),
};
export type FeaturePagePayload={
  title:string;
  description:string;
  metrics:Array<{label:string;value:string|number}>;
  links:Array<{label:string;href:string}>;
};
