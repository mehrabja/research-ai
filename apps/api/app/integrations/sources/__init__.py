"""Source discovery integrations."""
from app.integrations.sources.arxiv import ArxivProvider
from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
    SourceSearchProvider,
)
from app.integrations.sources.openalex import OpenAlexProvider
from app.integrations.sources.pubmed import PubMedProvider
from app.integrations.sources.semantic_scholar import (
    SemanticScholarProvider,
)

__all__ = [
    "ArxivProvider",
    "OpenAlexProvider",
    "PubMedProvider",
    "SemanticScholarProvider",
    "SourceProviderAuthError",
    "SourceProviderError",
    "SourceProviderInvalidResponseError",
    "SourceProviderRateLimitError",
    "SourceProviderTimeoutError",
    "SourceProviderUnavailableError",
    "SourceSearchProvider",
]
