"""Transactional email orchestration."""
from __future__ import annotations
import hashlib
from app.core.config import get_settings
from app.integrations.email.resend import ResendEmailProvider
from app.integrations.email.smtp import SMTPEmailProvider
def get_email_provider():
    p=get_settings().email_provider
    if p=="smtp": return SMTPEmailProvider()
    if p=="resend": return ResendEmailProvider()
    return None
def send_verification(*,to:str,token:str)->str|None:
    p=get_email_provider()
    if p is None: return None
    url=f"{get_settings().frontend_base_url.rstrip('/')}/verify-email?token={token}"
    return p.send(to=to,subject="Verify your Research AI email",text_body=f"Verify your Research AI account: {url}",idempotency_key="verify:"+hashlib.sha256(token.encode()).hexdigest())
def send_password_reset(*,to:str,token:str)->str|None:
    p=get_email_provider()
    if p is None: return None
    url=f"{get_settings().frontend_base_url.rstrip('/')}/reset-password?token={token}"
    return p.send(to=to,subject="Reset your Research AI password",text_body=f"Reset your Research AI password: {url}",idempotency_key="reset:"+hashlib.sha256(token.encode()).hexdigest())
def send_invitation(*,to:str,token:str,workspace_name:str)->str|None:
    p=get_email_provider()
    if p is None: return None
    url=f"{get_settings().frontend_base_url.rstrip('/')}/invite/{token}"
    return p.send(to=to,subject=f"Invitation to {workspace_name}",text_body=f"You were invited to {workspace_name} in Research AI: {url}",idempotency_key="invite:"+hashlib.sha256(token.encode()).hexdigest())
