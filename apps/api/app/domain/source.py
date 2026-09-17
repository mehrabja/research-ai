"""Domain-level source discovery contracts.

Framework-independent: no SQLAlchemy, no HTTP, no FastAPI.
The provider layer hands us raw JSON; we convert it into
``SourceCandidate`` before anything touches the database.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

_MAX_TITLE_LEN = 2000
_MIN_YEAR = 1000
_MAX_YEAR = 2200


def _normalize_doi(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    lower = s.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lower.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.strip().lower()
    return s or None


def _normalize_url(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        parsed = urlparse(s)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return s


def _normalize_year(raw: int | None) -> int | None:
    if raw is None or not isinstance(raw, int):
        return None
    if raw < _MIN_YEAR or raw > _MAX_YEAR:
        return None
    return raw


def _normalize_citation_count(raw: int | None) -> int | None:
    if raw is None or not isinstance(raw, int):
        return None
    return max(0, raw)


@dataclass(frozen=True)
class SourceIdentity:
    source_api: str
    external_source_id: str


@dataclass(frozen=True)
class SourceCandidate:
    """Provider-independent, normalized representation of one source.

    All normalization (trim, DOI prefix, URL scheme, year range,
    non-negative citation count) happens in ``__post_init__`` so that
    callers cannot accidentally persist un-normalized data.
    """

    source_api: str
    external_source_id: str
    title: str
    authors: tuple[str, ...] | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    citation_count: int | None = None
    source_meta: dict | None = None

    def __post_init__(self) -> None:
        api = (self.source_api or "").strip()
        if not api:
            raise ValueError("source_api is required")

        ext = (self.external_source_id or "").strip()
        if not ext:
            raise ValueError("external_source_id is required")

        title = (self.title or "").strip()
        if not title:
            raise ValueError("title is required")
        if len(title) > _MAX_TITLE_LEN:
            title = title[:_MAX_TITLE_LEN]

        object.__setattr__(self, "source_api", api)
        object.__setattr__(self, "external_source_id", ext)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "doi", _normalize_doi(self.doi))
        object.__setattr__(self, "url", _normalize_url(self.url))
        object.__setattr__(self, "year", _normalize_year(self.year))
        object.__setattr__(
            self,
            "citation_count",
            _normalize_citation_count(self.citation_count),
        )

        if self.authors is not None:
            cleaned = tuple(
                a.strip() for a in self.authors if a and a.strip()
            )
            object.__setattr__(
                self, "authors", cleaned if cleaned else None
            )

        if self.abstract is not None:
            ab = self.abstract.strip()
            object.__setattr__(self, "abstract", ab or None)

    def identity(self) -> SourceIdentity:
        return SourceIdentity(
            source_api=self.source_api,
            external_source_id=self.external_source_id,
        )


__all__ = [
    "SourceCandidate",
    "SourceIdentity",
]
