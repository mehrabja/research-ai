import type {Citation,Invitation,Manuscript,Member,Plan,Project,ProjectFileList,ProjectList,QA,RAGResponse,Report,Source,SourceCandidate,Usage,User,Workspace} from "./generated";

type ApiErrorBody={detail?:unknown;message?:unknown;error?:unknown};

function csrfCookie():string|undefined{
  if(typeof document==="undefined")return undefined;
  const prefix="research_ai_csrf=";
  return document.cookie.split("; ").find(x=>x.startsWith(prefix))?.slice(prefix.length);
}

async function rawRequest<T>(path:string,init?:RequestInit):Promise<Response>{
  const headers=new Headers(init?.headers);
  if(init?.body&&!headers.has("content-type"))headers.set("content-type","application/json");
  const csrf=csrfCookie();
  if(csrf&&!headers.has("X-CSRF-Token")&&init?.method&&init.method!=="GET"&&init.method!=="HEAD"){
    headers.set("X-CSRF-Token",csrf);
  }
  return fetch("/api/backend/"+path.replace(/^\//,""),{
    ...init,
    headers,
    cache:"no-store",
  });
}

async function parseError(res:Response):Promise<Error>{
  const body=await res.json().catch(()=>null) as ApiErrorBody|null;
  const raw=body?.detail??body?.message??body?.error??("Request failed ("+res.status+")");
  return new Error(typeof raw==="string"?raw:JSON.stringify(raw));
}

async function request<T>(path:string,init?:RequestInit,retry=true):Promise<T>{
  const res=await rawRequest<T>(path,init);
  if(res.status===401&&retry){
    const refresh=await fetch("/api/auth/refresh",{method:"POST",cache:"no-store"});
    if(refresh.ok)return request<T>(path,init,false);
  }
  if(!res.ok)throw await parseError(res);
  if(res.status===204)return undefined as T;
  return (await res.json()) as T;
}

export type DashboardStats={
  active_projects:number;saved_sources:number;evidence_items:number;
  active_jobs:number;storage_bytes:number;ai_generation_units:number;
  ai_generation_limit:number|null;workspace_count:number;
};
export type Notification={
  id:string;notification_type:string;title:string;body?:string|null;
  read_at?:string|null;created_at:string;
};
export type NotificationList={items:Notification[];total:number;unread:number};
export type SearchResponse={query:string;items:Array<{
  type:string;id:string;title:string;snippet?:string|null;
  workspace_id:string;project_id?:string|null;report_id?:string|null;
}>;total:number;limit:number;offset:number};

export const api={
  me:()=>request<User>("auth/me"),
  workspaces:()=>request<{items:Workspace[];total:number}>("workspaces"),
  createWorkspace:(name:string)=>request<Workspace>("workspaces",{method:"POST",body:JSON.stringify({name})}),
  dashboard:(w?:string)=>request<DashboardStats>("dashboard"+(w?"?workspace_id="+encodeURIComponent(w):"")),
  notifications:(w?:string)=>request<NotificationList>("notifications"+(w?"?workspace_id="+encodeURIComponent(w):"")),
  markNotificationRead:(id:string)=>request<void>("notifications/"+id+"/read",{method:"POST"}),
  readAllNotifications:(w?:string)=>request<void>("notifications/read-all"+(w?"?workspace_id="+encodeURIComponent(w):""),{method:"POST"}),
  notificationPreferences:(w?:string)=>request<Record<string,unknown>>("notifications/preferences"+(w?"?workspace_id="+encodeURIComponent(w):"")),
  updateNotificationPreferences:(body:object,w?:string)=>request<Record<string,unknown>>("notifications/preferences"+(w?"?workspace_id="+encodeURIComponent(w):""),{method:"PUT",body:JSON.stringify(body)}),

  globalSearch:(q:string,w?:string,limit=50,offset=0)=>request<SearchResponse>(
    "search?q="+encodeURIComponent(q)+(w?"&workspace_id="+encodeURIComponent(w):"")+"&limit="+limit+"&offset="+offset
  ),

  projects:(w:string)=>request<ProjectList>("projects?workspace_id="+encodeURIComponent(w)),
  project:(p:string,w:string)=>request<Project>("projects/"+p+"?workspace_id="+encodeURIComponent(w)),
  createProject:(w:string,b:object)=>request<Project>("projects?workspace_id="+encodeURIComponent(w),{method:"POST",body:JSON.stringify(b)}),
  projectReports:(p:string,w:string)=>request<{items:Array<{id:string;topic:string;status:string;output_language:string;updated_at:string}>;total:number}>("projects/"+p+"/reports?workspace_id="+encodeURIComponent(w)),
  reports:(w:string)=>request<Report[]>("reports?workspace_id="+encodeURIComponent(w)),
  report:(r:string)=>request<Report>("reports/"+r),

  sources:(r:string)=>request<{items:Source[]}>("reports/"+r+"/sources"),
  searchSources:(r:string,q:string,year?:number,openAccess=false)=>request<{query:string;limit:number;candidates:SourceCandidate[]}>("reports/"+r+"/sources/search?q="+encodeURIComponent(q)+"&limit=8"+(year?"&year="+year:"")+(openAccess?"&open_access=true":"")),
  createSource:(r:string,c:SourceCandidate)=>request<Source>("reports/"+r+"/sources",{method:"POST",body:JSON.stringify(c)}),

  literature:(p:string)=>request<unknown>("projects/"+p+"/literature"),
  knowledgeGraph:(p:string)=>request<unknown>("projects/"+p+"/knowledge-graph"),
  knowledgeGraphExport:(p:string,format:"json"|"csv")=>request<unknown>("projects/"+p+"/knowledge-graph/export?format="+format),

  evidenceMatrix:(r:string)=>request<unknown[]>("reports/"+r+"/evidence-matrix"),
  createEvidenceClaim:(r:string,b:object)=>request<unknown>("reports/"+r+"/evidence/claims",{method:"POST",body:JSON.stringify(b)}),

  folders:(p:string)=>request<unknown[]>("projects/"+p+"/file-folders"),
  createFolder:(p:string,b:object)=>request<unknown>("projects/"+p+"/file-folders",{method:"POST",body:JSON.stringify(b)}),
  files:(p:string)=>request<ProjectFileList>("projects/"+p+"/files"),
  uploadFile:(p:string,file:File,folderId?:string)=>{
    const form=new FormData();form.append("file",file);
    return request<unknown>("projects/"+p+"/files"+(folderId?"?folder_id="+encodeURIComponent(folderId):""),{method:"POST",body:form});
  },
  downloadFile:(id:string)=>fetch("/api/backend/files/"+id+"/content",{credentials:"same-origin",cache:"no-store"}),
  deleteFile:(id:string)=>request<void>("files/"+id,{method:"DELETE"}),

  plan:(p:string)=>request<unknown>("projects/"+p+"/research-plan"),
  planVersions:(p:string)=>request<unknown>("projects/"+p+"/research-plan/versions"),
  savePlan:(p:string,b:object)=>request<unknown>("projects/"+p+"/research-plan",{method:"PATCH",body:JSON.stringify(b)}),
  validatePlan:(p:string)=>request<unknown>("projects/"+p+"/research-plan/validate"),

  manuscript:(r:string)=>request<Manuscript>("reports/"+r+"/manuscript"),
  manuscriptDraft:(r:string)=>request<unknown>("reports/"+r+"/manuscript/draft"),
  autosaveManuscript:(r:string,b:object)=>request<unknown>("reports/"+r+"/manuscript/draft/autosave",{method:"PUT",body:JSON.stringify(b)}),
  saveManuscriptVersion:(r:string,b:object)=>request<unknown>("reports/"+r+"/manuscript/save-version",{method:"POST",body:JSON.stringify(b)}),

  generate:(r:string,b:object)=>request<unknown>("reports/"+r+"/generate",{method:"POST",body:JSON.stringify(b)}),
  humanize:(r:string,b:object)=>request<unknown>("reports/"+r+"/humanization/enqueue",{method:"POST",body:JSON.stringify(b)}),
  translate:(r:string,b:object)=>request<unknown>("reports/"+r+"/translation/enqueue",{method:"POST",body:JSON.stringify(b)}),

  jobs:(w?:string)=>request<unknown[]>("jobs"+(w?"?workspace_id="+encodeURIComponent(w):"")),
  enqueueJob:(jobType:string,payload:object,reportId?:string)=>request<unknown>("jobs",{method:"POST",body:JSON.stringify({job_type:jobType,payload,report_id:reportId})}),

  retryJob:(id:string)=>request<unknown>("jobs/"+id+"/retry",{method:"POST"}),
  cancelJob:(id:string)=>request<void>("jobs/"+id+"/cancel",{method:"POST"}),

  sessions:()=>request<unknown[]>("auth/sessions"),
  revokeSession:(id:string)=>request<void>("auth/sessions/"+id,{method:"DELETE"}),
  revokeOtherSessions:()=>request<void>("auth/sessions/revoke-others",{method:"POST"}),
  apiTokens:()=>request<unknown[]>("auth/api-tokens"),
  createApiToken:(body:object)=>request<unknown>("auth/api-tokens",{method:"POST",body:JSON.stringify(body)}),
  revokeApiToken:(id:string)=>request<void>("auth/api-tokens/"+id,{method:"DELETE"}),
  twoFactor:()=>request<unknown>("auth/2fa"),
  beginTwoFactor:()=>request<unknown>("auth/2fa/enroll",{method:"POST"}),
  confirmTwoFactor:(code:string)=>request<unknown>("auth/2fa/confirm",{method:"POST",body:JSON.stringify({code})}),
  disableTwoFactor:(code:string)=>request<unknown>("auth/2fa/disable",{method:"POST",body:JSON.stringify({code})}),
  members:(w:string)=>request<{items:Member[];total:number}>("workspaces/"+w+"/members"),
  manuscriptComments:(r:string,v:string)=>request<{items:unknown[];total:number}>("reports/"+r+"/manuscript-versions/"+v+"/comments"),
  addManuscriptComment:(r:string,v:string,body:object)=>request<unknown>("reports/"+r+"/manuscript-versions/"+v+"/comments",{method:"POST",body:JSON.stringify(body)}),
  resolveComment:(r:string,id:string)=>request<unknown>("reports/"+r+"/comments/"+id+"/resolve",{method:"POST"}),
  reviewTasks:(r:string,v:string)=>request<{items:unknown[];total:number}>("reports/"+r+"/manuscript-versions/"+v+"/reviews"),
  createReviewTask:(r:string,v:string,body:object)=>request<unknown>("reports/"+r+"/manuscript-versions/"+v+"/reviews",{method:"POST"}),
  updateReviewTask:(r:string,id:string,body:object)=>request<unknown>("reports/"+r+"/reviews/"+id,{method:"PATCH",body:JSON.stringify(body)}),
  changeMemberRole:(w:string,u:string,role:string)=>request<Member>("workspaces/"+w+"/members/"+u,{method:"PATCH",body:JSON.stringify({role})}),
  removeMember:(w:string,u:string)=>request<null>("workspaces/"+w+"/members/"+u,{method:"DELETE"}),
  invitations:(w:string)=>request<{items:Invitation[];total:number}>("workspaces/"+w+"/members/invitations"),
  invite:(w:string,b:object)=>request<{invitation:Invitation;token:string}>("workspaces/"+w+"/members/invitations",{method:"POST",body:JSON.stringify(b)}),
  revokeInvitation:(w:string,i:string)=>request<null>("workspaces/"+w+"/members/invitations/"+i,{method:"DELETE"}),
  transferOwnership:(w:string,u:string)=>request<Workspace>("workspaces/"+w+"/transfer-ownership",{method:"POST",body:JSON.stringify({target_user_id:u})}),

  usage:(w:string)=>request<Usage>("workspaces/"+w+"/usage"),
  planSubscription:(w:string)=>request<Plan>("workspaces/"+w+"/plan"),
  billingInvoices:(w:string)=>request<unknown[]>("workspaces/"+w+"/billing/invoices"),
  billingCheckout:(w:string,planCode:string)=>request<{provider:string;checkout_session_id:string;checkout_url:string}>("workspaces/"+w+"/billing/checkout",{method:"POST",body:JSON.stringify({plan_code:planCode})}),

  citations:(r:string)=>request<Citation>("reports/"+r+"/citations/current"),
  qa:(r:string)=>request<QA>("reports/"+r+"/academic-qa/current"),
  ragRetrieve:(p:string,b:object)=>request<RAGResponse>("projects/"+p+"/rag/retrieve",{method:"POST",body:JSON.stringify(b)}),
};
