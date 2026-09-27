import type{Citation,Invitation,Manuscript,Member,Plan,Project,ProjectList,QA,RAGResponse,Report,Source,SourceCandidate,Usage,User,Workspace}from"./generated";
async function request<T>(path:string,init?:RequestInit):Promise<T>{const res=await fetch("/api/backend/"+path.replace(/^\//,""),{...init,headers:{...(init?.body?{"content-type":"application/json"}:{}),...(init?.headers??{})},cache:"no-store"});const body=await res.json().catch(()=>null);if(!res.ok){const m=body?.detail??body?.message??("Request failed ("+res.status+")");throw new Error(typeof m==="string"?m:JSON.stringify(m))}return body as T}
export const api={
me:()=>request<User>("auth/me"),workspaces:()=>request<{items:Workspace[];total:number}>("workspaces"),createWorkspace:(name:string)=>request<Workspace>("workspaces",{method:"POST",body:JSON.stringify({name})}),
projects:(w:string)=>request<ProjectList>("projects?workspace_id="+encodeURIComponent(w)),project:(p:string,w:string)=>request<Project>("projects/"+p+"?workspace_id="+encodeURIComponent(w)),createProject:(w:string,b:object)=>request<Project>("projects?workspace_id="+encodeURIComponent(w),{method:"POST",body:JSON.stringify(b)}),
projectReports:(p:string,w:string)=>request<{items:Array<{id:string;topic:string;status:string;output_language:string;updated_at:string}>;total:number}>("projects/"+p+"/reports?workspace_id="+encodeURIComponent(w)),reports:(w:string)=>request<Report[]>("reports?workspace_id="+encodeURIComponent(w)),createReport:(w:string,b:object)=>request<Report>("reports?workspace_id="+encodeURIComponent(w),{method:"POST",body:JSON.stringify(b)}),report:(r:string)=>request<Report>("reports/"+r),
sources:(r:string)=>request<{items:Source[]}>("reports/"+r+"/sources"),searchSources:(r:string,q:string)=>request<{query:string;limit:number;candidates:SourceCandidate[]} >("reports/"+r+"/sources/search?q="+encodeURIComponent(q)+"&limit=8"),createSource:(r:string,c:SourceCandidate)=>request<Source>("reports/"+r+"/sources",{method:"POST",body:JSON.stringify(c)}),
ragRetrieve:(p:string,b:object)=>request<RAGResponse>("projects/"+p+"/rag/retrieve",{method:"POST",body:JSON.stringify(b)}),manuscript:(r:string)=>request<Manuscript>("reports/"+r+"/manuscript"),citations:(r:string)=>request<Citation>("reports/"+r+"/citations/current"),qa:(r:string)=>request<QA>("reports/"+r+"/academic-qa/current"),
members:(w:string)=>request<{items:Member[];total:number}>("workspaces/"+w+"/members"),changeMemberRole:(w:string,u:string,role:string)=>request<Member>("workspaces/"+w+"/members/"+u,{method:"PATCH",body:JSON.stringify({role})}),removeMember:(w:string,u:string)=>request<null>("workspaces/"+w+"/members/"+u,{method:"DELETE"}),invitations:(w:string)=>request<{items:Invitation[];total:number}>("workspaces/"+w+"/members/invitations"),invite:(w:string,b:object)=>request<{invitation:Invitation;token:string}>("workspaces/"+w+"/members/invitations",{method:"POST",body:JSON.stringify(b)}),revokeInvitation:(w:string,i:string)=>request<null>("workspaces/"+w+"/members/invitations/"+i,{method:"DELETE"}),transferOwnership:(w:string,u:string)=>request<Workspace>("workspaces/"+w+"/transfer-ownership",{method:"POST",body:JSON.stringify({target_user_id:u})}),usage:(w:string)=>request<Usage>("workspaces/"+w+"/usage"),plan:(w:string)=>request<Plan>("workspaces/"+w+"/plan"),
notifications:(w:string)=>request<{items:Array<{id:string;kind:string;title:string;body:string;read_at:string|null;created_at:string}>;total:number;unread:number}>("notifications?workspace_id="+encodeURIComponent(w)),
readNotification:(id:string)=>request<object>("notifications/"+id+"/read",{method:"POST"}),
readAllNotifications:(w:string)=>request<null>("notifications/read-all?workspace_id="+encodeURIComponent(w),{method:"POST"}),
createAPIToken:(b:{name:string;expires_at?:string|null})=>request<{id:string;name:string;token:string;token_prefix:string;expires_at:string|null}>("auth/api-tokens",{method:"POST",body:JSON.stringify(b)}),
apiTokens:()=>request<Array<{id:string;name:string;token_prefix:string;last_used_at:string|null;expires_at:string|null;revoked_at:string|null;created_at:string}>>("auth/api-tokens"),
revokeAPIToken:(id:string)=>request<null>("auth/api-tokens/"+id,{method:"DELETE"}),
search:(w:string,q:string)=>request<{query:string;items:Array<{id:string;resource_type:string;title:string;snippet:string|null;updated_at:string}>;total:number}>("search?workspace_id="+encodeURIComponent(w)+"&q="+encodeURIComponent(q)),
folders:(p:string)=>request<{items:Array<{id:string;project_id:string;parent_id:string|null;name:string;created_at:string;updated_at:string}>;total:number}>("projects/"+p+"/folders"),
jobs:()=>request<Array<{id:string;job_type:string;status:string;attempt_count:number;max_attempts:number;created_at:string;last_error_message:string|null}>>("jobs"),
};
export type FeaturePagePayload={
  title:string;
  description:string;
  metrics:Array<{label:string;value:string|number}>;
  links:Array<{label:string;href:string}>;
};
