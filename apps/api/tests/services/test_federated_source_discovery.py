from __future__ import annotations

import pytest

from app.domain.source import SourceCandidate
from app.integrations.sources.base import SourceProviderUnavailableError
from app.integrations.sources.federated import FederatedSourceSearchProvider


class _Provider:
    def __init__(self, name, candidates=None, error=None):
        self.provider_name = name
        self._candidates = candidates or []
        self._error = error

    def search(self, *, query, limit, year=None, open_access_only=False):
        if self._error:
            raise self._error
        return list(self._candidates)


def _candidate(*, source_api, ext, title, doi=None, abstract=None, citations=None, meta=None):
    return SourceCandidate(
        source_api=source_api,
        external_source_id=ext,
        title=title,
        doi=doi,
        abstract=abstract,
        citation_count=citations,
        source_meta=meta,
    )


def test_federated_dedupes_and_enriches_by_doi():
    a = _candidate(
        source_api="semantic_scholar",
        ext="s1",
        title="A Paper",
        doi="10.1000/test",
        abstract="short",
        citations=5,
    )
    b = _candidate(
        source_api="openalex",
        ext="o1",
        title="A Paper",
        doi="https://doi.org/10.1000/test",
        abstract="a much longer abstract",
        citations=12,
        meta={"venue": "Journal X", "is_open_access": True},
    )
    provider = FederatedSourceSearchProvider((
        _Provider("semantic_scholar", [a]),
        _Provider("openalex", [b]),
    ))

    out = provider.search(query="paper", limit=10)

    assert len(out) == 1
    assert out[0].doi == "10.1000/test"
    assert out[0].abstract == "a much longer abstract"
    assert out[0].citation_count == 12
    assert out[0].source_meta["venue"] == "Journal X"
    assert out[0].source_meta["federated"]["hit_count"] == 2


def test_federated_keeps_results_when_one_provider_is_down():
    good = _candidate(
        source_api="semantic_scholar",
        ext="s1",
        title="A Paper",
    )
    provider = FederatedSourceSearchProvider((
        _Provider("semantic_scholar", [good]),
        _Provider("crossref", error=SourceProviderUnavailableError()),
    ))

    out = provider.search(query="paper", limit=10)

    assert len(out) == 1
    assert out[0].source_meta["federated"]["provider_error_count"] == 1


def test_federated_raises_when_all_providers_fail():
    provider = FederatedSourceSearchProvider((
        _Provider("a", error=SourceProviderUnavailableError()),
        _Provider("b", error=SourceProviderUnavailableError()),
    ))

    with pytest.raises(SourceProviderUnavailableError):
        provider.search(query="paper", limit=10)
