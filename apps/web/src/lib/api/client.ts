import type {APIToken,APITokenCreateResponse,BillingInvoice,Citation,DetectionResult,EvidenceClaim,EvidenceLink,EvidenceMatrixItem,FileFolder,Invitation,Job,KnowledgeGraphNeighbor,KnowledgeGraphNodeList,KnowledgeGraphSummary,LiteratureCluster,LiteratureGap,LiteratureItem,LiteratureRun,Manuscript,ManuscriptVersion,Member,NotificationPreference,Session,Plan,PreTranslationReview,Project,ProjectFileList,ProjectList,ProjectFile,QA,RAGResponse,Report,ResearchPlan,ResearchPlanCoverage,ResearchPlanValidation,Source,SourceCandidate,SourceEmbedding,SourceExtraction,Subscription,TwoFactorEnrollment,Usage,User,Workspace} from "./generated";
import {routes} from "./routes";

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
  me:()=>request<User>(routes.me()),
  workspaces:()=>request<{items:Workspace[];total:number}>(routes.workspaces()),
  createWorkspace:(name:string)=>request<Workspace>(routes.createWorkspace(),{method:"POST",body:JSON.stringify({name})}),
  dashboard:(w?:string)=>request<DashboardStats>(routes.dashboard(w)),
  notifications:(w?:string)=>request<NotificationList>(routes.notifications(w)),
  markNotificationRead:(id:string)=>request<void>(routes.notificationRead(id),{method:"POST"}),
  readAllNotifications:(w?:string)=>request<void>(routes.notificationsReadAll(w),{method:"POST"}),
  notificationPreferences:(w?:string)=>request<NotificationPreference>(routes.notificationPreferences(w)),
  updateNotificationPreferences:(body:{channel:string;preferences:Record<string,boolean>},w?:string)=>request<NotificationPreference>(routes.notificationPreferences(w),{method:"PUT",body:JSON.stringify(body)}),

  globalSearch:(q:string,w?:string,limit=50,offset=0)=>request<SearchResponse>(routes.search(q,w,limit,offset)),

  projects:(w:string)=>request<ProjectList>(routes.projects(w)),
  project:(p:string,w:string)=>request<Project>(routes.project(p,w)),
  createProject:(w:string,b:object)=>request<Project>(routes.projects(w),{method:"POST",body:JSON.stringify(b)}),
  updateProject:(p:string,w:string,b:object)=>request<Project>(routes.project(p,w),{method:"PATCH",body:JSON.stringify(b)}),
  projectReports:(p:string,w:string)=>request<{items:Array<{id:string;topic:string;status:string;output_language:string;updated_at:string}>;total:number}>(routes.projectReports(p,w)),
  createReport:(w:string,b:object)=>request<Report>(routes.reports(w),{method:"POST",body:JSON.stringify(b)}),
  reports:(w:string)=>request<Report[]>(routes.reports(w)),
  report:(r:string)=>request<Report>(routes.report(r)),
  reportVersion:(r:string,v:string)=>request<{id:string;report_id:string;version_number:number;language:string;content:string;created_by_user:boolean;change_type:string|null;created_at:string}>(routes.reportVersion(r,v)),
  preTranslationReview:(r:string)=>request<PreTranslationReview>(routes.preTranslationReview(r)),

  sources:(r:string)=>request<{items:Source[]}>(routes.sources(r)),
  searchSources:(r:string,q:string,limit=25,year?:number,openAccess=false)=>request<{query:string;limit:number;candidates:SourceCandidate[]}>(routes.searchSources(r,q,limit,year,openAccess)),
  createSource:(r:string,c:SourceCandidate)=>request<Source>(routes.sources(r),{method:"POST",body:JSON.stringify(c)}),
  extractSource:(r:string,id:string)=>request<SourceExtraction>(routes.extractSource(r,id),{method:"POST"}),
  embedSource:(r:string,id:string)=>request<SourceEmbedding>(routes.embedSource(r,id),{method:"POST"}),

  literature:(p:string)=>request<{items:LiteratureItem[];total:number;limit:number;offset:number}>(routes.literature(p)),
  literatureAnalyze:(p:string,force=false)=>request<{status:string;job_id:string|null;run:LiteratureRun|null}>(routes.literatureAnalyze(p),{method:"POST",body:JSON.stringify({force})}),
  literatureClusters:(p:string)=>request<{items:LiteratureCluster[];total:number}>(routes.literatureClusters(p)),
  literatureGaps:(p:string)=>request<{items:LiteratureGap[];total:number}>(routes.literatureGaps(p)),
  literatureRuns:(p:string)=>request<{items:LiteratureRun[];total:number;limit:number;offset:number}>(routes.literatureRuns(p)),
  updateLiteratureItem:(p:string,id:string,b:{screening_status:"discovered"|"candidate"|"included"|"excluded"|"uncertain";reason?:string|null})=>request<LiteratureItem>(routes.literatureItem(p,id),{method:"PATCH",body:JSON.stringify(b)}),
  knowledgeGraph:(p:string)=>request<{id:string;project_id:string;version:number;status:string;graph_version:string;context_hash:string;source_literature_run_id:string|null;research_plan_id:string|null;node_count:number;edge_count:number;graph_meta:Record<string,unknown>|null;created_by:string|null;created_at:string;updated_at:string}>(routes.knowledgeGraph(p)),
  knowledgeGraphSummary:(p:string)=>request<KnowledgeGraphSummary>(routes.knowledgeGraphSummary(p)),
  knowledgeGraphNodes:(p:string,search="",nodeType="",limit=100,offset=0)=>request<KnowledgeGraphNodeList>(routes.knowledgeGraphNodes(p)+"?limit="+limit+"&offset="+offset+(search?"&search="+encodeURIComponent(search):"")+(nodeType?"&node_type="+encodeURIComponent(nodeType):"")),
  knowledgeGraphNeighbors:(p:string,nodeId:string)=>request<KnowledgeGraphNeighbor[]>(routes.knowledgeGraphNodeNeighbors(p,nodeId)+"?limit=50"),
  knowledgeGraphQuery:(p:string,b:{start_node_id:string;max_depth?:number;max_nodes?:number;relation_types?:string[]})=>request<import("./generated").KnowledgeGraphQueryResponse>(routes.knowledgeGraphQuery(p),{method:"POST",body:JSON.stringify(b)}),
  knowledgeGraphExport:async(p:string,format:"json"|"csv"):Promise<Blob>=>{
    const response=await fetch("/api/backend/"+routes.knowledgeGraphExport(p)+"?format="+encodeURIComponent(format),{credentials:"same-origin",cache:"no-store"});
    if(!response.ok)throw new Error("Knowledge graph export failed ("+response.status+").");
    return response.blob();
  },
  detection:(r:string,v:string)=>request<DetectionResult>(routes.detection(r,v)),
  enqueueDetection:(r:string,v:string)=>request<{job_id:string;report_id:string;version_id:string;status:"queued"}>(routes.detectionGenerate(r,v),{method:"POST"}),
  ragReadiness:(p:string)=>request<import("./generated").RAGReadiness>(routes.ragReadiness(p)),
  ragRetrieve:(p:string,b:object)=>request<RAGResponse>(routes.ragRetrieve(p),{method:"POST",body:JSON.stringify(b)}),
  ragRuns:(p:string,limit=25,offset=0)=>request<{items:import("./generated").RetrievalRun[];total:number;limit:number;offset:number}>(routes.ragRuns(p,limit,offset)),
  ragRun:(p:string,id:string)=>request<RAGResponse>(routes.ragRun(p,id)),

  evidenceMatrix:(r:string)=>request<EvidenceMatrixItem[]>(routes.evidenceMatrix(r)),
  createEvidenceClaim:(r:string,b:object)=>request<EvidenceClaim>(routes.evidenceClaims(r),{method:"POST",body:JSON.stringify(b)}),
  linkEvidence:(r:string,claimId:string,b:object)=>request<EvidenceLink>(routes.evidenceLinks(r,claimId),{method:"POST",body:JSON.stringify(b)}),
  unlinkEvidence:(r:string,claimId:string,linkId:string)=>request<void>(routes.evidenceLink(r,claimId,linkId),{method:"DELETE"}),

  folders:(p:string)=>request<FileFolder[]>(routes.folders(p)),
  createFolder:(p:string,b:object)=>request<FileFolder>(routes.folders(p),{method:"POST",body:JSON.stringify(b)}),
  updateFolder:(p:string,id:string,b:object)=>request<FileFolder>(routes.folder(p,id),{method:"PATCH",body:JSON.stringify(b)}),
  deleteFolder:(p:string,id:string)=>request<void>(routes.folder(p,id),{method:"DELETE"}),
  files:(p:string)=>request<ProjectFileList>(routes.files(p)),
  uploadFile:(p:string,file:File,folderIdOrOptions?:string|UploadOptions,maybeOptions?:UploadOptions):Promise<ProjectFile>=>{
    const options:UploadOptions=typeof folderIdOrOptions==="string"
      ? {...(maybeOptions??{}),folderId:folderIdOrOptions}
      : (folderIdOrOptions??{});
    const query=options.folderId?"?folder_id="+encodeURIComponent(options.folderId):"";
    const path="/api/backend/"+routes.files(p)+query;

    return new Promise<ProjectFile>((resolve,reject)=>{
      if(options.signal?.aborted){reject(new UploadCancelledError());return;}

      const xhr=new XMLHttpRequest();
      let settled=false;
      let lastProgressPercent=-1;

      const abort=()=>{if(!settled)xhr.abort();};
      const handleProgress=(event:ProgressEvent<XMLHttpRequestEventTarget>)=>{
        const total=event.total;
        const loaded=event.loaded;
        if(total>0){
          const percent=Math.min(100,(loaded/total)*100);
          if(percent!==lastProgressPercent){
            lastProgressPercent=percent;
            options.onProgress?.({loaded,total,percent});
          }
        }
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
            if(lastProgressPercent<100){
              lastProgressPercent=100;
              options.onProgress?.({loaded:file.size,total:file.size,percent:100});
            }
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
  downloadFile:(id:string)=>fetch("/api/backend/"+routes.fileContent(id),{credentials:"same-origin",cache:"no-store"}),
  updateFile:(id:string,b:object)=>request<ProjectFile>(routes.file(id),{method:"PATCH",body:JSON.stringify(b)}),
  deleteFile:(id:string)=>request<void>(routes.file(id),{method:"DELETE"}),

  plan:(p:string)=>request<ResearchPlan>(routes.plan(p)),
  planVersions:(p:string)=>request<{items:ResearchPlan[];total:number;limit:number;offset:number}>(routes.planVersions(p)),
  savePlan:(p:string,b:object)=>request<ResearchPlan>(routes.plan(p),{method:"PATCH",body:JSON.stringify(b)}),
  validatePlan:(p:string)=>request<ResearchPlanValidation>(routes.planValidate(p)),
  planCoverage:(p:string)=>request<ResearchPlanCoverage>(routes.planCoverage(p)),

  manuscript:(r:string)=>request<Manuscript>(routes.manuscript(r)),
  manuscriptVersions:(r:string)=>request<{items:ManuscriptVersion[];total:number;limit:number;offset:number}>(routes.manuscriptVersions(r)),
  manuscriptProseCurrent:(r:string)=>request<import("./generated").ManuscriptProseCurrent>(routes.manuscriptProseCurrent(r)),
  manuscriptProseGenerate:(r:string,b:{base_manuscript_version_id:string;mode?:string;force?:boolean;async?:boolean})=>request<{status:string;job_id:string|null;run_id:string|null;context_hash:string|null;section_count:number|null;word_count:number|null}>(routes.manuscriptProseGenerate(r),{method:"POST",body:JSON.stringify(b)}),
  manuscriptProseValidate:(r:string)=>request<import("./generated").ManuscriptValidation>(routes.manuscriptProseValidate(r)),
  manuscriptDraft:(r:string)=>request<{revision:number;base_version_id:string|null;content:unknown}>(routes.manuscriptDraft(r)),
  autosaveManuscript:(r:string,b:object)=>request<{conflict?:boolean;draft:{revision:number;base_version_id:string|null;content:unknown}}>(routes.manuscriptDraftAutosave(r),{method:"PUT",body:JSON.stringify(b)}),
  saveManuscriptVersion:(r:string,b:object)=>request<unknown>(routes.manuscriptSaveVersion(r),{method:"POST",body:JSON.stringify(b)}),
  restoreManuscriptVersion:(r:string,v:string,b:{expected_revision:number})=>request<{saved:boolean;conflict:boolean;draft:{revision:number;base_version_id:string|null;content:unknown}}>(routes.manuscriptRestoreVersion(r,v),{method:"POST",body:JSON.stringify(b)}),

  generate:(r:string,b:{brief?:string})=>request<Job>(routes.jobsEnqueue(),{method:"POST",body:JSON.stringify({job_type:"generate_report",payload:{report_id:r,...b},report_id:r})}),
  humanize:(r:string,b:{version_id:string;detection_run_id:string;policy_version?:string})=>request<{job_id:string;status:"queued"}>(routes.humanizationEnqueue(r),{method:"POST",body:JSON.stringify(b)}),
  humanizationCurrent:(r:string)=>request<import("./generated").HumanizationCurrent>(routes.humanizationCurrent(r)),
  translate:(r:string,b:{source_version_id:string;target_language:string})=>request<{job_id:string;status:"queued"}>(routes.translationEnqueue(r),{method:"POST",body:JSON.stringify(b)}),
  translationCurrent:(r:string)=>request<import("./generated").TranslationCurrent>(routes.translationCurrent(r)),

  jobs:(w?:string)=>request<Job[]>(routes.jobs(w)),
  job:(id:string)=>request<Job>(routes.job(id)),
  enqueueJob:(jobType:string,payload:object,reportId?:string)=>request<Job>(routes.jobsEnqueue(),{method:"POST",body:JSON.stringify({job_type:jobType,payload,report_id:reportId})}),

  retryJob:(id:string)=>request<Job>(routes.jobsRetry(id),{method:"POST"}),
  cancelJob:(id:string)=>request<{job:Job}>(routes.jobsCancel(id),{method:"POST"}),

  sessions:()=>request<{items:Session[];total:number}>(routes.sessions()),
  revokeSession:(id:string)=>request<void>(routes.session(id),{method:"DELETE"}),
  revokeOtherSessions:()=>request<void>(routes.sessionsRevokeOthers(),{method:"POST"}),
  apiTokens:()=>request<APIToken[]>(routes.apiTokens()),
  createApiToken:(body:object)=>request<APITokenCreateResponse>(routes.apiTokens(),{method:"POST",body:JSON.stringify(body)}),
  revokeApiToken:(id:string)=>request<void>(routes.apiToken(id),{method:"DELETE"}),
  twoFactor:()=>request<{enabled:boolean}>(routes.twoFactor()),
  beginTwoFactor:()=>request<TwoFactorEnrollment>(routes.twoFactorEnroll(),{method:"POST"}),
  confirmTwoFactor:(code:string)=>request<{enabled:boolean}>(routes.twoFactorConfirm(),{method:"POST",body:JSON.stringify({code})}),
  disableTwoFactor:(code:string)=>request<{enabled:boolean}>(routes.twoFactorDisable(),{method:"POST",body:JSON.stringify({code})}),
  members:(w:string)=>request<{items:Member[];total:number}>(routes.members(w)),
  manuscriptComments:(r:string,v:string)=>request<import("./generated").ManuscriptCommentList>(routes.manuscriptComments(r,v)),
  addManuscriptComment:(r:string,v:string,body:object)=>request<unknown>(routes.manuscriptComments(r,v),{method:"POST",body:JSON.stringify(body)}),
  resolveComment:(r:string,id:string)=>request<unknown>(routes.resolveComment(r,id),{method:"POST"}),
  reopenComment:(r:string,id:string)=>request<unknown>(routes.reopenComment(r,id),{method:"POST"}),
  reviewTasks:(r:string,v:string)=>request<import("./generated").ManuscriptReviewTaskList>(routes.reviewTasks(r,v)),
  createReviewTask:(r:string,v:string,body:object)=>request<unknown>(routes.reviewTasks(r,v),{method:"POST"}),
  updateReviewTask:(r:string,id:string,body:object)=>request<unknown>(routes.updateReviewTask(r,id),{method:"PATCH",body:JSON.stringify(body)}),
  changeMemberRole:(w:string,u:string,role:string)=>request<Member>(routes.member(w,u),{method:"PATCH",body:JSON.stringify({role})}),
  removeMember:(w:string,u:string)=>request<null>(routes.member(w,u),{method:"DELETE"}),
  invitations:(w:string)=>request<{items:Invitation[];total:number}>(routes.invitations(w)),
  invite:(w:string,b:object)=>request<{invitation:Invitation;token:string}>(routes.invitations(w),{method:"POST",body:JSON.stringify(b)}),
  acceptInvitation:(token:string)=>request<{workspace_id:string;user_id:string;role:string;status:string}>(routes.acceptInvitation(token),{method:"POST"}),
  revokeInvitation:(w:string,i:string)=>request<null>(routes.invitation(w,i),{method:"DELETE"}),
  transferOwnership:(w:string,u:string)=>request<Workspace>(routes.transferOwnership(w),{method:"POST",body:JSON.stringify({target_user_id:u})}),

  usage:(w:string)=>request<Usage>(routes.usage(w)),
  subscription:(w:string)=>request<Subscription>(routes.subscription(w)),
  planSubscription:(w:string)=>request<Plan>(routes.planSubscription(w)),
  billingInvoices:(w:string)=>request<{items:BillingInvoice[];total:number}>(routes.billingInvoices(w)),
  billingCheckout:(w:string,planCode:string)=>request<{provider:string;checkout_session_id:string;checkout_url:string}>(routes.billingCheckout(w),{method:"POST",body:JSON.stringify({plan_code:planCode})}),
  billingChangePlan:(w:string,planCode:string)=>request<Subscription>(routes.billingChangePlan(w),{method:"POST",body:JSON.stringify({plan_code:planCode})}),
  billingCancel:(w:string)=>request<Subscription>(routes.billingCancel(w),{method:"POST"}),
  billingResume:(w:string)=>request<Subscription>(routes.billingResume(w),{method:"POST"}),

  citations:(r:string)=>request<Citation>(routes.citationsCurrent(r)),
  qa:(r:string)=>request<QA>(routes.qaCurrent(r)),
};
