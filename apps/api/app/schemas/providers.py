from __future__ import annotations

from pydantic import BaseModel


class ProviderCapabilityRead(BaseModel):
    capability: str
    configured_preferred: str
    available_providers: list[str]


class ProviderMatrixRead(BaseModel):
    capabilities: list[ProviderCapabilityRead]
