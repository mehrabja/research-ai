"""M39 OAuth routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth_security import OAuthStartResponse
from app.services import oauth
from app.db.models.user import User

router=APIRouter(prefix="/auth/oauth",tags=["oauth"])

@router.get("/{provider}",response_model=OAuthStartResponse)
def start(provider:str,db:Session=Depends(get_db))->OAuthStartResponse:
    return OAuthStartResponse(provider=provider,authorization_url=oauth.start(db,provider=provider))

@router.get("/{provider}/callback")
def callback(provider:str,code:str,state:str,request:Request,db:Session=Depends(get_db)):
    user,access,refresh,csrf=oauth.callback(db,provider=provider,code=code,state=state,user_agent=request.headers.get("user-agent"),ip=request.client.host if request.client else None)
    s=get_settings()
    target=RedirectResponse(s.frontend_base_url.rstrip("/")+"/oauth/success")
    target.set_cookie(s.auth_refresh_cookie_name,refresh,httponly=True,secure=s.auth_refresh_secure_cookie,samesite=s.auth_refresh_same_site,path="/",max_age=s.jwt_refresh_token_expire_days*86400)
    target.set_cookie(s.auth_csrf_cookie_name,csrf,httponly=False,secure=s.auth_refresh_secure_cookie,samesite=s.auth_refresh_same_site,path="/",max_age=s.jwt_refresh_token_expire_days*86400)
    target.set_cookie("research_ai_access_token",access,httponly=True,secure=s.auth_refresh_secure_cookie,samesite=s.auth_refresh_same_site,path="/",max_age=s.jwt_access_token_expire_minutes*60)
    return target
