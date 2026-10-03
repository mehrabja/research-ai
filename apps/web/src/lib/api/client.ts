import type {APIToken,APITokenCreateResponse,BillingInvoice,Citation,EvidenceClaim,EvidenceLink,EvidenceMatrixItem,FileFolder,Invitation,KnowledgeGraphNeighbor,KnowledgeGraphNodeList,KnowledgeGraphSummary,LiteratureCluster,LiteratureGap,LiteratureItem,LiteratureRun,Manuscript,Member,Plan,Project,ProjectFileList,ProjectList,ProjectFile,QA,RAGResponse,Report,ResearchPlan,ResearchPlanCoverage,ResearchPlanValidation,Source,SourceCandidate,SourceEmbedding,SourceExtraction,Subscription,TwoFactorEnrollment,Usage,User,Workspace} from "./generated";

type ApiErrorBody={detail?:unknown;message?:unknown;error?:unknown};

function isRecord(value:unknown):value is Record<string,unknown>{
  return typeof value==="object"&&value!==null&&!Array.isArray(value);
}

function stringValue(value:unknown):string|undefined{
  return typeof value==="string"&&value.trim()?value:undefined;
}

export class ApiRequestError extends Error{
  readonly status:number;
  readonly code?:string;
  readonly requestId?:string;
  readonly retryAfter?:number;

  constructor(message:string,status:number,opts?:{code?:string;requestId?:string;retryAfter?:number}){
    super(message);
    this.name="ApiRequestError";
    this.status=status;
    this.code=opts?.code;
    this.requestId=opts?.requestId;
    this.retryAfter=opts?.retryAfter;
  }
}

export class UploadCancelledError extends Error{
  constructor(){
    super("Upload cancelled.");
    this.name="UploadCancelledError";
  }
}

export type UploadProgress={loaded:number;total:number;percent:number};

export type UploadOptions={
  folderId?:string;
  signal?:AbortSignal;
  onProgress?:(progress:UploadProgress)=>void;
};

function isProjectFile(value:unknown):value is ProjectFile{
  if(!isRecord(value))return false;
  return typeof value.id==="string"
    && typeof value.project_id==="string"
    && (typeof value.folder_id==="string"||value.folder_id===null)
    && typeof value.original_filename==="string"
    && typeof value.normalized_filename==="string"
    && (typeof value.extension==="string"||value.extension===null)
    && typeof value.storage_provider==="string"
    && typeof value.sha256==="string"
    && (typeof value.client_mime_type==="string"||value.client_mime_type===null)
    && (typeof value.detected_mime_type==="string"||value.detected_mime_type===null)
    && typeof value.size_bytes==="number"
    && typeof value.status==="string"
    && typeof value.extraction_status==="string"
    && (typeof value.extraction_error==="string"||value.extraction_error===null)
    && (typeof value.extraction_pipeline_version==="string"||value.extraction_pipeline_version===null)
    && typeof value.file_kind==="string"
    && typeof value.created_at==="string"
    && typeof value.updated_at==="string"
    && (typeof value.deleted_at==="string"||value.deleted_at===null);
}

function csrfCookie():string|undefined{
  if(typeof document==="undefined")return undefined;
  const prefix="research_ai_csrf=";
  return document.cookie.split("; ").find(x=>x.startsWith(prefix))?.slice(prefix.length);
}

async function rawRequest<T>(path:string,init?:RequestInit):Promise<Response>{
  const headers=new Headers(init?.headers);
  if(init?.body&&!headers.has("content-type")&&!(typeof FormData!=="undefined"&&init.body instanceof FormData)){
    headers.set("content-type","application/json");
  }
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

async function parseError(res:Response):Promise<ApiRequestError>{
  const body:unknown=await res.json().catch(()=>null);
  let message="Request failed ("+res.status+").";
  let code:string|undefined;
  let requestId=res.headers.get("X-Request-ID")??undefined;
  let retryAfterRaw=res.headers.get("Retry-After");
  let retryAfter=retryAfterRaw?Number(retryAfterRaw):undefined;

  if(isRecord(body)){
    const nested=isRecord(body.error)?body.error:undefined;
    const candidate=stringValue(nested?.message)??stringValue(body.message)??stringValue(body.detail);
    if(candidate)message=candidate;
    code=stringValue(nested?.code)??stringValue(body.code);
    requestId=stringValue(nested?.request_id)??requestId;
    const nestedRetry=nested?.retry_after;
    if(typeof nestedRetry==="number"&&Number.isFinite(nestedRetry))retryAfter=nestedRetry;
  }

  return new ApiRequestError(message,res.status,{code,requestId,retryAfter:Number.isFinite(retryAfter??NaN)?retryAfter:undefined});
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
  updateProject:(p:string,w:string,b:object)=>request<Project>("projects/"+p+"?workspace_id="+encodeURIComponent(w),{method:"PATCH",body:JSON.stringify(b)}),
  projectReports:(p:string,w:string)=>request<{items:Array<{id:string;topic:string;status:string;output_language:string;updated_at:string}>;total:number}>("projects/"+p+"/reports?workspace_id="+encodeURIComponent(w)),
  createReport:(w:string,b:object)=>request<Report>("reports?workspace_id="+encodeURIComponent(w),{method:"POST",body:JSON.stringify(b)}),
  reports:(w:string)=>request<Report[]>("reports?workspace_id="+encodeURIComponent(w)),
  report:(r:string)=>request<Report>("reports/"+r),

  sources:(r:string)=>request<{items:Source[]}>("reports/"+r+"/sources"),
  searchSources:(r:string,q:string,limit=25,year?:number,openAccess=false)=>request<{query:string;limit:number;candidates:SourceCandidate[]}>("reports/"+r+"/sources/search?q="+encodeURIComponent(q)+"&limit="+Math.max(1,Math.min(1000,Math.floor(limit)))+(year?"&year="+year:"")+(openAccess?"&open_access=true":"")),
  createSource:(r:string,c:SourceCandidate)=>request<Source>("reports/"+r+"/sources",{method:"POST",body:JSON.stringify(c)}),
  extractSource:(r:string,id:string)=>request<SourceExtraction>("reports/"+r+"/sources/"+id+"/extract",{method:"POST"}),
  embedSource:(r:string,id:string)=>request<SourceEmbedding>("reports/"+r+"/sources/"+id+"/embed",{method:"POST"}),

  literature:(p:string)=>request<{items:LiteratureItem[];total:number;limit:number;offset:number}>("projects/"+p+"/literature"),
  literatureAnalyze:(p:string,force=false)=>request<{status:string;job_id:string|null;run:LiteratureRun|null}>("projects/"+p+"/literature/analyze",{method:"POST",body:JSON.stringify({force})}),
  literatureClusters:(p:string)=>request<{items:LiteratureCluster[];total:number}>("projects/"+p+"/literature/clusters"),
  literatureGaps:(p:string)=>request<{items:LiteratureGap[];total:number}>("projects/"+p+"/literature/gaps"),
  literatureRuns:(p:string)=>request<{items:LiteratureRun[];total:number;limit:number;offset:number}>("projects/"+p+"/literature/runs"),
  updateLiteratureItem:(p:string,id:string,b:{screening_status:"discovered"|"candidate"|"included"|"excluded"|"uncertain";reason?:string|null})=>request<LiteratureItem>("projects/"+p+"/literature/"+id,{method:"PATCH",body:JSON.stringify(b)}),
  knowledgeGraph:(p:string)=>request<{id:string;project_id:string;version:number;status:string;graph_version:string;context_hash:string;source_literature_run_id:string|null;research_plan_id:string|null;node_count:number;edge_count:number;graph_meta:Record<string,unknown>|null;created_by:string|null;created_at:string;updated_at:string}>("projects/"+p+"/knowledge-graph"),
  knowledgeGraphSummary:(p:string)=>request<KnowledgeGraphSummary>("projects/"+p+"/knowledge-graph/summary"),
  knowledgeGraphNodes:(p:string,search="",nodeType="",limit=100,offset=0)=>request<KnowledgeGraphNodeList>("projects/"+p+"/knowledge-graph/nodes?limit="+limit+"&offset="+offset+(search?"&search="+encodeURIComponent(search):"")+(nodeType?"&node_type="+encodeURIComponent(nodeType):"")),
  knowledgeGraphNeighbors:(p:string,nodeId:string)=>request<KnowledgeGraphNeighbor[]>("projects/"+p+"/knowledge-graph/nodes/"+nodeId+"/neighbors?limit=50"),
  knowledgeGraphExport:(p:string,format:"json"|"csv")=>request<unknown>("projects/"+p+"/knowledge-graph/export?format="+format),
  ragReadiness:(p:string)=>request<import("./generated").RAGReadiness>("projects/"+p+"/rag/readiness"),
  ragRetrieve:(p:string,b:object)=>request<RAGResponse>("projects/"+p+"/rag/retrieve",{method:"POST",body:JSON.stringify(b)}),

  evidenceMatrix:(r:string)=>request<EvidenceMatrixItem[]>("reports/"+r+"/evidence-matrix"),
  createEvidenceClaim:(r:string,b:object)=>request<EvidenceClaim>("reports/"+r+"/evidence/claims",{method:"POST",body:JSON.stringify(b)}),
  linkEvidence:(r:string,claimId:string,b:object)=>request<EvidenceLink>("reports/"+r+"/evidence/claims/"+claimId+"/links",{method:"POST",body:JSON.stringify(b)}),

  folders:(p:string)=>request<FileFolder[]>("projects/"+p+"/file-folders"),
  createFolder:(p:string,b:object)=>request<FileFolder>("projects/"+p+"/file-folders",{method:"POST",body:JSON.stringify(b)}),
  updateFolder:(p:string,id:string,b:object)=>request<FileFolder>("projects/"+p+"/file-folders/"+id,{method:"PATCH",body:JSON.stringify(b)}),
  deleteFolder:(p:string,id:string)=>request<void>("projects/"+p+"/file-folders/"+id,{method:"DELETE"}),
  files:(p:string)=>request<ProjectFileList>("projects/"+p+"/files"),
  uploadFile:(p:string,file:File,folderIdOrOptions?:string|UploadOptions,maybeOptions?:UploadOptions):Promise<ProjectFile>=>{
    const options:UploadOptions=typeof folderIdOrOptions==="string"
      ? {...(maybeOptions??{}),folderId:folderIdOrOptions}
      : (folderIdOrOptions??{});
    const query=options.folderId?"?folder_id="+encodeURIComponent(options.folderId):"";
    const path="/api/backend/projects/"+encodeURIComponent(p)+"/files"+query;

    return new Promise<ProjectFile>((resolve,reject)=>{
      if(options.signal?.aborted){reject(new UploadCancelledError());return;}

      const xhr=new XMLHttpRequest();
      let settled=false;

      const abort=()=>{if(!settled)xhr.abort();};
      const handleProgress=()=>{
        const total=xhr.upload.total;
        if(total>0)options.onProgress?.({loaded:xhr.upload.loaded,total,percent:Math.min(100,(xhr.upload.loaded/total)*100)});
      };
      const cleanup=()=>{
        options.signal?.removeEventListener("abort",abort);
        xhr.upload.removeEventListener("progress",handleProgress);
      };
      const fail=(error:Error)=>{
        if(settled)return;
        settled=true;cleanup();reject(error);
      };

      xhr.open("POST",path,true);
      xhr.withCredentials=true;
      xhr.setRequestHeader("Accept","application/json");
      const csrf=csrfCookie();
      if(csrf)xhr.setRequestHeader("X-CSRF-Token",csrf);
      xhr.upload.addEventListener("progress",handleProgress);
      options.signal?.addEventListener("abort",abort,{once:true});

      xhr.addEventListener("load",async()=>{
        if(settled)return;
        const status=xhr.status;
        const requestId=xhr.getResponseHeader("X-Request-ID")??undefined;
        if(status>=200&&status<300){
          try{
            const parsed:unknown=xhr.responseText?JSON.parse(xhr.responseText):null;
            if(!isProjectFile(parsed)){
              fail(new ApiRequestError("Upload completed but the file response did not match the API contract.",status,{requestId}));
              return;
            }
            settled=true;cleanup();
            options.onProgress?.({loaded:file.size,total:file.size,percent:100});
            resolve(parsed);
          }catch{
            fail(new ApiRequestError("Upload completed but the server response could not be read.",status,{requestId}));
          }
          return;
        }

        let body:unknown=null;
        if(xhr.responseText){
          try{body=JSON.parse(xhr.responseText) as unknown;}catch{body=null;}
        }
        const nested=isRecord(body)&&isRecord(body.error)?body.error:undefined;
        const message=(isRecord(body)?stringValue(nested?.message)??stringValue(body.message)??stringValue(body.detail):undefined)??("Upload failed ("+status+").");
        const retryAfterHeader=xhr.getResponseHeader("Retry-After");
        const retryAfter=retryAfterHeader?Number(retryAfterHeader):undefined;
        fail(new ApiRequestError(message,status,{
          code:stringValue(nested?.code)??(isRecord(body)?stringValue(body.code):undefined),
          requestId:stringValue(nested?.request_id)??requestId,
          retryAfter:Number.isFinite(retryAfter??NaN)?retryAfter:undefined,
        }));
      });
      xhr.addEventListener("error",()=>fail(new ApiRequestError("Network error while uploading. Check your connection and retry.",0)));
      xhr.addEventListener("abort",()=>fail(new UploadCancelledError()));

      const form=new FormData();
      form.append("file",file);
      xhr.send(form);
    });
  },
  downloadFile:(id:string)=>fetch("/api/backend/files/"+id+"/content",{credentials:"same-origin",cache:"no-store"}),
  updateFile:(id:string,b:object)=>request<ProjectFile>("files/"+id,{method:"PATCH",body:JSON.stringify(b)}),
  deleteFile:(id:string)=>request<void>("files/"+id,{method:"DELETE"}),

  plan:(p:string)=>request<ResearchPlan>("projects/"+p+"/research-plan"),
  planVersions:(p:string)=>request<{items:ResearchPlan[];total:number;limit:number;offset:number}>("projects/"+p+"/research-plan/versions"),
  savePlan:(p:string,b:object)=>request<ResearchPlan>("projects/"+p+"/research-plan",{method:"PATCH",body:JSON.stringify(b)}),
  validatePlan:(p:string)=>request<ResearchPlanValidation>("projects/"+p+"/research-plan/validate"),
  planCoverage:(p:string)=>request<ResearchPlanCoverage>("projects/"+p+"/research-plan/coverage"),

  manuscript:(r:string)=>request<Manuscript>("reports/"+r+"/manuscript"),
  manuscriptDraft:(r:string)=>request<{revision:number;base_version_id:string|null;content:unknown}>("reports/"+r+"/manuscript/draft"),
  autosaveManuscript:(r:string,b:object)=>request<{conflict?:boolean;draft:{revision:number;base_version_id:string|null;content:unknown}}>("reports/"+r+"/manuscript/draft/autosave",{method:"PUT",body:JSON.stringify(b)}),
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
  apiTokens:()=>request<APIToken[]>("auth/api-tokens"),
  createApiToken:(body:object)=>request<APITokenCreateResponse>("auth/api-tokens",{method:"POST",body:JSON.stringify(body)}),
  revokeApiToken:(id:string)=>request<void>("auth/api-tokens/"+id,{method:"DELETE"}),
  twoFactor:()=>request<{enabled:boolean}>("auth/2fa"),
  beginTwoFactor:()=>request<TwoFactorEnrollment>("auth/2fa/enroll",{method:"POST"}),
  confirmTwoFactor:(code:string)=>request<{enabled:boolean}>("auth/2fa/confirm",{method:"POST",body:JSON.stringify({code})}),
  disableTwoFactor:(code:string)=>request<{enabled:boolean}>("auth/2fa/disable",{method:"POST",body:JSON.stringify({code})}),
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
  subscription:(w:string)=>request<Subscription>("workspaces/"+w+"/subscription"),
  planSubscription:(w:string)=>request<Plan>("workspaces/"+w+"/plan"),
  billingInvoices:(w:string)=>request<{items:BillingInvoice[];total:number}>("workspaces/"+w+"/billing/invoices"),
  billingCheckout:(w:string,planCode:string)=>request<{provider:string;checkout_session_id:string;checkout_url:string}>("workspaces/"+w+"/billing/checkout",{method:"POST",body:JSON.stringify({plan_code:planCode})}),

  citations:(r:string)=>request<Citation>("reports/"+r+"/citations/current"),
  qa:(r:string)=>request<QA>("reports/"+r+"/academic-qa/current"),
  ragRetrieve:(p:string,b:object)=>request<RAGResponse>("projects/"+p+"/rag/retrieve",{method:"POST",body:JSON.stringify(b)}),
};
