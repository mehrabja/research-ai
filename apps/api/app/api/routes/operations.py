"""M39 dashboard, project export and audit activity routes."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from sqlalchemy import func, select, union_all
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_current_user
from app.db.models.job import Job
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report, ReportEvent
from app.db.models.source import Source
from app.db.models.user import User
from app.db.session import get_db
from app.domain.workspace import WORKSPACE_STATUS_ACTIVE
from app.schemas.operations import AuditEventListResponse, AuditEventRead, DashboardSummary, ProjectExportManifest
from app.services import entitlements as entitlements_service
from app.services import usage as usage_service
from app.services.workspaces import get_workspace_for_user

router=APIRouter(tags=["operations"])


@router.get("/workspaces/{workspace_id}/dashboard",response_model=DashboardSummary)
def dashboard(workspace_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->DashboardSummary:
    ws,_=get_workspace_for_user(db,workspace_id=workspace_id,user_id=current_user.id)
    pcount=int(db.execute(select(func.count()).select_from(Project).where(Project.workspace_id==workspace_id,Project.status!="archived")).scalar_one())
    rcount=int(db.execute(select(func.count()).select_from(Report).join(Project,Project.id==Report.project_id).where(Project.workspace_id==workspace_id,Report.deleted_at.is_(None))).scalar_one())
    fcount=int(db.execute(select(func.count()).select_from(ProjectFile).join(Project,Project.id==ProjectFile.project_id).where(Project.workspace_id==workspace_id,ProjectFile.deleted_at.is_(None))).scalar_one())
    storage=int(db.execute(select(func.coalesce(func.sum(ProjectFile.size_bytes),0)).select_from(ProjectFile).join(Project,Project.id==ProjectFile.project_id).where(Project.workspace_id==workspace_id,ProjectFile.deleted_at.is_(None))).scalar_one())
    jobs=int(db.execute(select(func.count()).select_from(Job).where(Job.user_id==current_user.id,Job.status.in_(("queued","processing","retrying")))).scalar_one())
    start,end=usage_service.period_bounds_utc()
    metrics={}
    for metric in ("reports_created","ai_generation_units","search_requests"):
        metrics[metric]=usage_service.get_period_usage(db,workspace_id=workspace_id,metric=metric,period_start=start,period_end=end)
    plan=entitlements_service.resolve_active_plan(db,workspace_id=workspace_id)
    return DashboardSummary(workspace_id=ws.id,projects=pcount,reports=rcount,files=fcount,storage_bytes=storage,active_jobs=jobs,current_plan=plan.code if plan else "none",usage=metrics)


@router.get("/workspaces/{workspace_id}/audit",response_model=AuditEventListResponse)
def audit(workspace_id:uuid.UUID,limit:int=Query(default=50,ge=1,le=200),current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->AuditEventListResponse:
    get_workspace_for_user(db,workspace_id=workspace_id,user_id=current_user.id)
    project_rows=db.execute(select(ProjectEvent,Project.workspace_id).join(Project,Project.id==ProjectEvent.project_id).where(Project.workspace_id==workspace_id).order_by(ProjectEvent.created_at.desc()).limit(limit)).all()
    report_rows=db.execute(select(ReportEvent,Project.workspace_id).join(Report,Report.id==ReportEvent.report_id).join(Project,Project.id==Report.project_id).where(Project.workspace_id==workspace_id).order_by(ReportEvent.created_at.desc()).limit(limit)).all()
    items=[]
    for e,_ in project_rows:
        items.append(AuditEventRead(id=str(e.id),source="project",event_type=e.event_type,user_id=e.user_id,project_id=e.project_id,report_id=None,created_at=e.created_at,metadata=e.event_meta))
    for e,_ in report_rows:
        items.append(AuditEventRead(id=str(e.id),source="report",event_type=e.event_type,user_id=e.user_id,project_id=None,report_id=e.report_id,created_at=e.created_at,metadata=e.event_meta))
    items.sort(key=lambda x:x.created_at,reverse=True)
    return AuditEventListResponse(items=items[:limit],total=len(items[:limit]))


@router.get("/projects/{project_id}/export",response_model=ProjectExportManifest)
def export_project(project_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->ProjectExportManifest:
    project=db.execute(select(Project).where(Project.id==project_id,Project.user_id==current_user.id)).scalar_one_or_none()
    if project is None:
        from app.core.exceptions import ProjectNotFound
        raise ProjectNotFound()
    files=list(db.execute(select(ProjectFile).where(ProjectFile.project_id==project_id,ProjectFile.deleted_at.is_(None)).order_by(ProjectFile.created_at.asc())).scalars().all())
    reports=list(db.execute(select(Report).where(Report.project_id==project_id,Report.deleted_at.is_(None)).order_by(Report.created_at.asc())).scalars().all())
    report_ids=[r.id for r in reports]
    sources=list(db.execute(select(Source).where(Source.report_id.in_(report_ids))).scalars().all()) if report_ids else []
    return ProjectExportManifest(
        project={"id":str(project.id),"name":project.name,"description":project.description,"domain":project.domain,"research_objective":project.research_objective,"research_questions":project.research_questions,"hypotheses":project.hypotheses,"scope":project.scope,"constraints":project.constraints,"status":project.status},
        files=[{"id":str(f.id),"filename":f.original_filename,"kind":f.file_kind,"size_bytes":f.size_bytes,"sha256":f.sha256,"status":f.status,"extraction_status":f.extraction_status,"folder_id":str(f.folder_id) if f.folder_id else None} for f in files],
        reports=[{"id":str(r.id),"topic":r.topic,"domain":r.domain,"status":r.status,"output_language":r.output_language,"created_at":r.created_at.isoformat()} for r in reports],
        sources=[{"id":str(s.id),"title":s.title,"doi":s.doi,"url":s.url,"year":s.year,"citation_count":s.citation_count,"status":s.status} for s in sources],
        generated_at=datetime.now(UTC),
    )
