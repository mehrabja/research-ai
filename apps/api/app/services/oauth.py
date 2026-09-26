"""OAuth2/OIDC identity adapters for Google and GitHub login."""
from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationRequired, AppError
from app.core.security import hash_password
from app.db.models.auth import OAuthAccount, OAuthState
from app.db.models.user import User
from app.services.auth_sessions import issue_session
from app.services import workspaces

class OAuthUnavailable(AppError):
    code="OAUTH_UNAVAILABLE"; status_code=503; message="OAuth provider is not configured."
class OAuthInvalidState(AppError):
    code="OAUTH_INVALID_STATE"; status_code=400; message="OAuth state is invalid or expired."
class OAuthProviderError(AppError):
    code="OAUTH_PROVIDER_ERROR"; status_code=502; message="OAuth provider request failed."

PROVIDERS={"google","github"}

def _sha(v:str)->str:
    return hashlib.sha256(v.encode()).hexdigest()

def _config(provider:str)->tuple[str,str,str,list[str]]:
    s=get_settings()
    if provider=="google":
        if not s.oauth_google_client_id or not s.oauth_google_client_secret: raise OAuthUnavailable()
        return s.oauth_google_client_id,s.oauth_google_client_secret,"https://oauth2.googleapis.com/token",["openid","email","profile"]
    if provider=="github":
        if not s.oauth_github_client_id or not s.oauth_github_client_secret: raise OAuthUnavailable()
        return s.oauth_github_client_id,s.oauth_github_client_secret,"https://github.com/login/oauth/access_token",["read:user","user:email"]
    raise OAuthUnavailable("Unsupported OAuth provider.")

def _callback(provider:str)->str:
    s=get_settings()
    base=s.oauth_redirect_base_url.rstrip("/") or (s.frontend_base_url.rstrip("/") + "/api/v1")
    return f"{base}/auth/oauth/{provider}/callback"

def start(db:Session, *, provider:str)->str:
    if provider not in PROVIDERS: raise OAuthUnavailable()
    client_id,_,_,scopes=_config(provider)
    state=secrets.token_urlsafe(32)
    row=OAuthState(provider=provider,state_hash=_sha(state),redirect_uri=_callback(provider),expires_at=datetime.now(UTC)+timedelta(minutes=10))
    db.add(row); db.commit()
    if provider=="google":
        params={"client_id":client_id,"redirect_uri":row.redirect_uri,"response_type":"code","scope":" ".join(scopes),"state":state,"access_type":"online","prompt":"select_account"}
        return "https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(params)
    params={"client_id":client_id,"redirect_uri":row.redirect_uri,"scope":" ".join(scopes),"state":state}
    return "https://github.com/login/oauth/authorize?"+urlencode(params)

def _state(db:Session, *, provider:str, state:str)->OAuthState:
    row=db.execute(select(OAuthState).where(OAuthState.provider==provider,OAuthState.state_hash==_sha(state),OAuthState.used_at.is_(None)).with_for_update()).scalar_one_or_none()
    if row is None or row.expires_at<=datetime.now(UTC): raise OAuthInvalidState()
    row.used_at=datetime.now(UTC); db.flush(); return row

def _exchange(provider:str, *, code:str, redirect_uri:str)->tuple[str,dict]:
    s=get_settings()
    if provider=="google":
        payload={"code":code,"client_id":s.oauth_google_client_id,"client_secret":s.oauth_google_client_secret,"redirect_uri":redirect_uri,"grant_type":"authorization_code"}
        url="https://oauth2.googleapis.com/token"
    else:
        payload={"code":code,"client_id":s.oauth_github_client_id,"client_secret":s.oauth_github_client_secret,"redirect_uri":redirect_uri}
        url="https://github.com/login/oauth/access_token"
    try:
        r=httpx.post(url,data=payload,headers={"Accept":"application/json"},timeout=15)
    except httpx.HTTPError as exc: raise OAuthProviderError(type(exc).__name__) from exc
    if r.status_code>=400: raise OAuthProviderError(f"HTTP {r.status_code}")
    data=r.json()
    token=data.get("access_token")
    if not isinstance(token,str): raise OAuthProviderError("provider did not return an access token")
    return token,data

def _identity(provider:str, token:str)->tuple[str,str|None,bool,str|None]:
    try:
        if provider=="google":
            r=httpx.get("https://openidconnect.googleapis.com/v1/userinfo",headers={"Authorization":f"Bearer {token}"},timeout=15)
            if r.status_code>=400: raise OAuthProviderError(f"userinfo HTTP {r.status_code}")
            data=r.json(); sub=data.get("sub"); email=data.get("email"); verified=bool(data.get("email_verified"))
            return str(sub), str(email) if email else None, verified, data.get("name")
        r=httpx.get("https://api.github.com/user",headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"},timeout=15)
        if r.status_code>=400: raise OAuthProviderError(f"user HTTP {r.status_code}")
        data=r.json(); sub=data.get("id")
        er=httpx.get("https://api.github.com/user/emails",headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"},timeout=15)
        if er.status_code>=400: raise OAuthProviderError(f"emails HTTP {er.status_code}")
        emails=er.json() if isinstance(er.json(),list) else []
        verified_rows=[x for x in emails if x.get("verified")]
        primary=next((x for x in verified_rows if x.get("primary")),None) or (verified_rows[0] if verified_rows else None)
        email=primary.get("email") if primary else data.get("email")
        return str(sub), email, bool(primary and primary.get("verified")), data.get("name")
    except httpx.HTTPError as exc:
        raise OAuthProviderError(type(exc).__name__) from exc

def callback(db:Session, *, provider:str, code:str, state:str, user_agent:str|None, ip:str|None)->tuple[User,str,str,str]:
    st=_state(db,provider=provider,state=state)
    token,_=_exchange(provider,code=code,redirect_uri=st.redirect_uri)
    provider_user_id,email,verified,name=_identity(provider,token)
    if not email or not verified: raise OAuthProviderError("provider account does not expose a verified email")
    account=db.execute(select(OAuthAccount).where(OAuthAccount.provider==provider,OAuthAccount.provider_user_id==provider_user_id)).scalar_one_or_none()
    if account is not None:
        user=db.get(User,account.user_id)
    else:
        user=db.execute(select(User).where(__import__("sqlalchemy").func.lower(User.email)==email.lower())).scalar_one_or_none()
        if user is None:
            user=User(email=email,password_hash=hash_password(secrets.token_urlsafe(32)),full_name=name,email_verified_at=datetime.now(UTC))
            db.add(user); db.flush()
        else:
            user.email_verified_at=user.email_verified_at or datetime.now(UTC)
        account=OAuthAccount(user_id=user.id,provider=provider,provider_user_id=provider_user_id,provider_email=email,provider_metadata={"display_name":name})
        db.add(account); db.flush()
    _,refresh,csrf=issue_session(db,user_id=user.id,user_agent=user_agent,ip=ip)
    workspaces.ensure_default_workspace(db,user_id=user.id)
    db.commit()
    from app.core.security import create_access_token
    return user,create_access_token(subject=str(user.id)),refresh,csrf
