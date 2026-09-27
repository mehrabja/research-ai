from __future__ import annotations

from pydantic import BaseModel, Field


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    recovery_codes: list[str]


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=12)


class MFAStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int


class MFADisableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=32)
