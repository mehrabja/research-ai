from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.user import User
from app.providers.registry import ProviderCapability, get_provider_registry
from app.schemas.providers import ProviderCapabilityRead, ProviderMatrixRead

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/matrix", response_model=ProviderMatrixRead)
def provider_matrix(
    current_user: User = Depends(get_current_user),
) -> ProviderMatrixRead:
    settings = get_settings()
    registry = get_provider_registry()
    preferred = {
        ProviderCapability.GENERATION.value: settings.generation_provider,
        ProviderCapability.EMBEDDING.value: settings.embedding_provider,
        ProviderCapability.TRANSLATION.value: settings.translation_provider,
        ProviderCapability.DETECTION.value: settings.detection_provider,
        ProviderCapability.SOURCE_DISCOVERY.value: settings.source_discovery_provider,
        ProviderCapability.BILLING.value: settings.billing_provider,
    }
    rows = [
        ProviderCapabilityRead(
            capability=capability.value,
            configured_preferred=preferred.get(capability.value, ""),
            available_providers=list(registry.providers(capability)),
        )
        for capability in ProviderCapability
    ]
    return ProviderMatrixRead(capabilities=rows)
