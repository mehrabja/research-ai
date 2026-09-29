from __future__ import annotations

from pydantic import BaseModel, Field


class OAuthStartResponse(BaseModel):
    provider: str
    authorization_url: str
    state: str
    code_verifier: str


class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=4096)
    state: str = Field(..., min_length=16, max_length=512)
    code_verifier: str = Field(..., min_length=43, max_length=128)
