"""M39 workspace-scoped global search."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.search import GlobalSearchResponse, SearchResultRead
from app.services.workspaces import get_workspace_for_user

router=APIRouter(prefix="/search",tags=["search"])

@router.get("",response_model=GlobalSearchResponse)
def global_search(workspace_id:uuid.UUID,q:str=Query(min_length=1,max_length=200),limit:int=Query(default=30,ge=1,le=100),current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->GlobalSearchResponse:
    get_workspace_for_user(db,workspace_id=workspace_id,user_id=current_user.id)
    needle=f"%{q.strip()}%"
    items:list[SearchResultRead]=[]
    projects=db.execute(select(Project).where(Project.workspace_id==workspace_id,Project.user_id==current_user.id,or_(Project.name.ilike(needle),Project.description.ilike(needle))).limit(limit)).scalars().all()
    items.extend(SearchResultRead(kind="project",id=p.id,title=p.name,subtitle=p.description) for p in projects)
    remaining=max(0,limit-len(items))
    if remaining:
        reports=db.execute(select(Report).join(Project,Project.id==Report.project_id).where(Project.workspace_id==workspace_id,Report.user_id==current_user.id,or_(Report.topic.ilike(needle),Report.domain.ilike(needle))).limit(remaining)).scalars().all()
        items.extend(SearchResultRead(kind="report",id=r.id,title=r.topic,subtitle=r.status,project_id=r.project_id) for r in reports)
    remaining=max(0,limit-len(items))
    if remaining:
        sources=db.execute(select(Source).join(Report,Report.id==Source.report_id).join(Project,Project.id==Report.project_id).where(Project.workspace_id==workspace_id,Report.user_id==current_user.id,or_(Source.title.ilike(needle),Source.doi.ilike(needle))).limit(remaining)).scalars().all()
        items.extend(SearchResultRead(kind="source",id=s.id,title=s.title,subtitle=s.doi) for s in sources)
    remaining=max(0,limit-len(items))
    if remaining:
        rows=db.execute(select(ProjectFile).join(Project,Project.id==ProjectFile.project_id).where(Project.workspace_id==workspace_id,Project.user_id==current_user.id,ProjectFile.deleted_at.is_(None),ProjectFile.normalized_filename.ilike(needle)).limit(remaining)).scalars().all()
        items.extend(SearchResultRead(kind="file",id=f.id,title=f.original_filename,subtitle=f.file_kind,project_id=f.project_id) for f in rows)
    return GlobalSearchResponse(query=q.strip(),items=items,total=len(items))
