"""M39 project file folders."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.exceptions import AppError, ProjectNotFound
from app.db.models.file_folder import FileFolder
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.folders import FolderCreate, FolderListResponse, FolderRead

router=APIRouter(prefix="/projects",tags=["files"])

def _project(db:Session,project_id:uuid.UUID,user_id:uuid.UUID)->Project:
    p=db.execute(select(Project).where(Project.id==project_id,Project.user_id==user_id)).scalar_one_or_none()
    if p is None: raise ProjectNotFound()
    return p

def _depth(db:Session,folder:FileFolder)->int:
    depth=0; cur=folder
    while cur.parent_folder_id is not None:
        depth+=1
        if depth>32: break
        cur=db.execute(select(FileFolder).where(FileFolder.id==cur.parent_folder_id,FileFolder.project_id==folder.project_id)).scalar_one_or_none()
        if cur is None: break
    return depth

@router.get("/{project_id}/folders",response_model=FolderListResponse)
def list_folders(project_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->FolderListResponse:
    _project(db,project_id,current_user.id)
    rows=list(db.execute(select(FileFolder).where(FileFolder.project_id==project_id).order_by(FileFolder.name.asc())).scalars().all())
    return FolderListResponse(items=[FolderRead.model_validate(r) for r in rows],total=len(rows))

@router.post("/{project_id}/folders",response_model=FolderRead,status_code=201)
def create_folder(project_id:uuid.UUID,body:FolderCreate,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->FolderRead:
    _project(db,project_id,current_user.id)
    if body.parent_folder_id:
        parent=db.execute(select(FileFolder).where(FileFolder.id==body.parent_folder_id,FileFolder.project_id==project_id)).scalar_one_or_none()
        if parent is None: raise AppError("Parent folder not found.",code="FOLDER_NOT_FOUND")
        if _depth(db,parent)+1>=8: raise AppError("Folder nesting limit reached.",code="FOLDER_DEPTH_EXCEEDED",status_code=422)
    name=body.name.strip()
    existing=db.execute(select(FileFolder).where(FileFolder.project_id==project_id,FileFolder.parent_folder_id==body.parent_folder_id,FileFolder.name==name)).scalar_one_or_none()
    if existing is not None: raise AppError("Folder already exists.",code="FOLDER_ALREADY_EXISTS",status_code=409)
    row=FileFolder(project_id=project_id,parent_folder_id=body.parent_folder_id,name=name,created_by=current_user.id)
    db.add(row);db.commit();db.refresh(row)
    return FolderRead.model_validate(row)

@router.delete("/folders/{folder_id}",status_code=204)
def delete_folder(folder_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->None:
    row=db.execute(select(FileFolder).join(Project,Project.id==FileFolder.project_id).where(FileFolder.id==folder_id,Project.user_id==current_user.id)).scalar_one_or_none()
    if row is None: raise AppError("Folder not found.",code="FOLDER_NOT_FOUND",status_code=404)
    db.delete(row);db.commit()
