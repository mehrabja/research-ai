"""Federated literature discovery across configured source providers."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderError,
    SourceSearchProvider,
)

_WS_RE = re.compile(r"\s+")


def _norm_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold()
    return _WS_RE.sub(" ", value).strip()


def _dedupe_key(candidate: SourceCandidate) -> str:
    if candidate.doi:
        return f"doi:{candidate.doi}"
    title = _norm_text(candidate.title)
    first_author = _norm_text(
        candidate.authors[0] if candidate.authors else None
    )
    return f"title:{title}|year:{candidate.year or 0}|author:{first_author}"


@dataclass
class _MergedCandidate:
    candidate: SourceCandidate
    providers: list[str]
    hits: list[dict[str, object]]
    abstracts: list[str]
    citation_counts: list[int]
    dois: list[str]
    metadata: list[dict[str, object]]


class FederatedSourceSearchProvider:
    """Fan-out, merge, dedupe and enrich source candidates."""

    provider_name = "federated"

    def __init__(
        self,
        providers: tuple[SourceSearchProvider, ...],
    ) -> None:
        if not providers:
            raise ValueError("at least one source provider is required")
        self._providers = providers

    @property
    def providers(self) -> tuple[SourceSearchProvider, ...]:
        return self._providers

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        merged: dict[str, _MergedCandidate] = {}
        errors: list[SourceProviderError] = []
        successes = 0

        for provider_index, provider in enumerate(self._providers):
            try:
                candidates = provider.search(
                    query=query,
                    limit=limit,
                    year=year,
                    open_access_only=open_access_only,
                )
                successes += 1
            except SourceProviderError as exc:
                errors.append(exc)
                continue

            for provider_rank, candidate in enumerate(candidates, start=1):
                key = _dedupe_key(candidate)
                row = merged.get(key)
                meta = dict(candidate.source_meta or {})
                if row is None:
                    merged[key] = _MergedCandidate(
                        candidate=candidate,
                        providers=[candidate.source_api],
                        hits=[{
                            "source_api": candidate.source_api,
                            "external_source_id": candidate.external_source_id,
                            "rank": provider_rank,
                            "provider_index": provider_index,
                        }],
                        abstracts=[candidate.abstract] if candidate.abstract else [],
                        citation_counts=[candidate.citation_count] if candidate.citation_count is not None else [],
                        dois=[candidate.doi] if candidate.doi else [],
                        metadata=[meta],
                    )
                    continue

                if candidate.source_api not in row.providers:
                    row.providers.append(candidate.source_api)
                row.hits.append({
                    "source_api": candidate.source_api,
                    "external_source_id": candidate.external_source_id,
                    "rank": provider_rank,
                    "provider_index": provider_index,
                })
                if candidate.abstract:
                    row.abstracts.append(candidate.abstract)
                if candidate.citation_count is not None:
                    row.citation_counts.append(candidate.citation_count)
                if candidate.doi:
                    row.dois.append(candidate.doi)
                row.metadata.append(meta)

        if not merged and successes == 0 and errors:
            raise errors[-1]

        output: list[tuple[float, SourceCandidate]] = []
        for row in merged.values():
            base = row.candidate
            merged_meta = _merge_metadata(row.metadata)
            merged_meta["federated"] = {
                "providers": row.providers,
                "hit_count": len(row.hits),
                "provider_hits": row.hits,
                "provider_error_count": len(errors),
            }
            abstract = max(row.abstracts, key=len) if row.abstracts else base.abstract
            citation_count = max(row.citation_counts) if row.citation_counts else base.citation_count
            doi = base.doi or (row.dois[0] if row.dois else None)
            output.append((
                _federated_score(row.hits, citation_count),
                SourceCandidate(
                    source_api=base.source_api,
                    external_source_id=base.external_source_id,
                    title=base.title,
                    authors=base.authors,
                    year=base.year,
                    doi=doi,
                    url=base.url,
                    abstract=abstract,
                    citation_count=citation_count,
                    source_meta=merged_meta,
                ),
            ))

        output.sort(key=lambda item: (
            -item[0],
            -(item[1].citation_count or -1),
            -(item[1].year or -1),
            _norm_text(item[1].title),
            item[1].external_source_id,
        ))
        return [candidate for _, candidate in output[:limit]]


def _federated_score(
    hits: list[dict[str, object]],
    citation_count: int | None,
) -> float:
    hit_bonus = float(len(hits))
    ranks = [rank for h in hits if isinstance((rank := h.get("rank")), int)]
    best_rank = min(ranks) if ranks else 1
    rank_bonus = 1.0 / max(1, best_rank)
    citation_bonus = min(5.0, float(citation_count or 0) / 1000.0)
    return hit_bonus + rank_bonus + citation_bonus


def _merge_metadata(metadata: list[dict[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key in ("venue", "journal", "publication_type", "language"):
        value = next(
            (str(meta[key]).strip() for meta in metadata if meta.get(key) not in (None, "")),
            None,
        )
        if value:
            out[key] = value
    oa_values = [meta.get("is_open_access") for meta in metadata if "is_open_access" in meta]
    if oa_values:
        out["is_open_access"] = any(bool(value) for value in oa_values)
    return out


__all__ = ["FederatedSourceSearchProvider"]
