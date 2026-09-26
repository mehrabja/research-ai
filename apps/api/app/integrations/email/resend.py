"""Resend transactional email adapter."""
from __future__ import annotations
import httpx
from app.core.config import get_settings
from app.integrations.email.base import EmailAuthenticationError, EmailInvalidRequestError, EmailProviderError, EmailRateLimitError, EmailUnavailableError
class ResendEmailProvider:
    provider_name="resend"
    def __init__(self)->None:
        s=get_settings(); self.api_key,self.base_url,self.sender=s.resend_api_key,s.resend_base_url.rstrip("/"),s.email_from_address
    def send(self, *, to:str, subject:str, text_body:str, html_body:str|None=None, idempotency_key:str|None=None)->str|None:
        if not self.api_key or not self.sender: raise EmailProviderError("Resend is not configured")
        payload={"from":self.sender,"to":[to],"subject":subject,"text":text_body}
        if html_body: payload["html"]=html_body
        headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"}
        if idempotency_key: headers["Idempotency-Key"]=idempotency_key
        try: r=httpx.post(self.base_url+"/emails",json=payload,headers=headers,timeout=20)
        except httpx.HTTPError as exc: raise EmailUnavailableError(type(exc).__name__) from exc
        if r.status_code in (401,403): raise EmailAuthenticationError(f"HTTP {r.status_code}")
        if r.status_code==429: raise EmailRateLimitError("HTTP 429")
        if r.status_code>=500: raise EmailUnavailableError(f"HTTP {r.status_code}")
        if r.status_code>=400: raise EmailInvalidRequestError(f"HTTP {r.status_code}")
        data=r.json(); return data.get("id")
