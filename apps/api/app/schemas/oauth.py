from __future__ import annotations

from pydantic import BaseModel, Field


class OAuthStartResponse(BaseModel):
    provider: str
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=4096)
    state: str = Field(..., min_length=16, max_length=512)
