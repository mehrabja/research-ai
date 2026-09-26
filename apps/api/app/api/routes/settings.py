"""M39 security and account settings endpoints."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.models.api_token import ApiToken
from app.db.models.auth import AuthSession
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth_security import ApiTokenCreate, ApiTokenCreated, ApiTokenRead, SessionListResponse, SessionRead, TotpSetupResponse, TotpStatusResponse, TotpVerifyRequest
from app.services import api_tokens, auth_sessions, two_factor

router=APIRouter(prefix="/settings/security",tags=["security"])

@router.get("/sessions",response_model=SessionListResponse)
def list_sessions(current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->SessionListResponse:
    rows=list(db.execute(select(AuthSession).where(AuthSession.user_id==current_user.id).order_by(AuthSession.last_seen_at.desc())).scalars().all())
    return SessionListResponse(items=[SessionRead.model_validate(x) for x in rows],total=len(rows))

@router.delete("/sessions/{session_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->None:
    auth_sessions.revoke_session_by_id(db,user_id=current_user.id,session_id=session_id)

@router.get("/api-tokens",response_model=list[ApiTokenRead])
def list_tokens(current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->list[ApiTokenRead]:
    rows=list(db.execute(select(ApiToken).where(ApiToken.user_id==current_user.id).order_by(ApiToken.created_at.desc())).scalars().all())
    return [ApiTokenRead.model_validate(x) for x in rows]

@router.post("/api-tokens",response_model=ApiTokenCreated,status_code=status.HTTP_201_CREATED)
def create_token(body:ApiTokenCreate,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->ApiTokenCreated:
    row,raw=api_tokens.create_token(db,user_id=current_user.id,label=body.label,expires_at=body.expires_at)
    db.commit(); db.refresh(row)
    return ApiTokenCreated(token=raw,token_info=ApiTokenRead.model_validate(row))

@router.delete("/api-tokens/{token_id}",status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->None:
    api_tokens.revoke_token(db,user_id=current_user.id,token_id=token_id)

@router.get("/2fa",response_model=TotpStatusResponse)
def get_2fa(current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->TotpStatusResponse:
    enabled,remaining=two_factor.status(db,user_id=current_user.id)
    return TotpStatusResponse(enabled=enabled,recovery_codes_remaining=remaining)

@router.post("/2fa/setup",response_model=TotpSetupResponse)
def setup_2fa(current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->TotpSetupResponse:
    secret,url=two_factor.begin_setup(db,user_id=current_user.id,email=current_user.email)
    return TotpSetupResponse(secret=secret,issuer=two_factor.issuer(),account_name=current_user.email,otpauth_url=url)

@router.post("/2fa/verify",response_model=TotpStatusResponse)
def verify_2fa(body:TotpVerifyRequest,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->TotpStatusResponse:
    _,codes=two_factor.enable(db,user_id=current_user.id,code=body.code)
    return TotpStatusResponse(enabled=True,recovery_codes_remaining=len(codes))

@router.delete("/2fa",response_model=TotpStatusResponse)
def disable_2fa(current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->TotpStatusResponse:
    two_factor.disable(db,user_id=current_user.id)
    return TotpStatusResponse(enabled=False,recovery_codes_remaining=0)
