"""SMTP transactional email adapter."""
from __future__ import annotations
import smtplib
from email.message import EmailMessage
from app.core.config import get_settings
from app.integrations.email.base import EmailInvalidRequestError, EmailProviderError
class SMTPEmailProvider:
    provider_name="smtp"
    def __init__(self)->None:
        s=get_settings(); self.host,self.port,self.username,self.password=s.smtp_host,s.smtp_port,s.smtp_username,s.smtp_password; self.use_tls=s.smtp_use_tls; self.sender=s.email_from_address
    def send(self, *, to:str, subject:str, text_body:str, html_body:str|None=None, idempotency_key:str|None=None)->str|None:
        if not self.host or not self.sender: raise EmailProviderError("SMTP is not configured")
        if not to or not subject or not text_body: raise EmailInvalidRequestError("email fields are incomplete")
        msg=EmailMessage(); msg["From"]=self.sender; msg["To"]=to; msg["Subject"]=subject; msg.set_content(text_body)
        if html_body: msg.add_alternative(html_body, subtype="html")
        try:
            with smtplib.SMTP(self.host,self.port,timeout=20) as client:
                if self.use_tls: client.starttls()
                if self.username: client.login(self.username,self.password)
                client.send_message(msg)
        except (OSError,smtplib.SMTPException) as exc: raise EmailProviderError(type(exc).__name__) from exc
        return None
