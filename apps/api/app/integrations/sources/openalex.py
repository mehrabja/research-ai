from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_settings
from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderInvalidResponseError,
    SourceProviderUnavailableError,
)


class OpenAlexProvider:
    provider_name = "openalex"

    def __init__(self) -> None:
        settings = get_settings()
        self._mailto = settings.crossref_mailto
        self._base_url = "https://api.openalex.org/works"
        self._timeout = 20.0

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        params = {
            "search": query,
            "per-page": str(max(1, min(limit, 100))),
        }
        if year is not None:
            params["filter"] = f"from_publication_year:{year},to_publication_year:{year}"
        if open_access_only:
            params["filter"] = ((params.get("filter") + ",") if params.get("filter") else "") + "is_oa:true"
        if self._mailto:
            params["mailto"] = self._mailto
        req = urllib.request.Request(
            self._base_url + "?" + urllib.parse.urlencode(params),
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            raise SourceProviderUnavailableError(
                f"OpenAlex request failed: {type(exc).__name__}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceProviderInvalidResponseError(
                "OpenAlex returned invalid JSON"
            ) from exc

        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise SourceProviderInvalidResponseError(
                "OpenAlex response missing results list"
            )

        candidates: list[SourceCandidate] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title = item.get("display_name")
            work_id = item.get("id")
            if not isinstance(title, str) or not isinstance(work_id, str):
                continue
            authors: list[str] = []
            for authorship in item.get("authorships") or []:
                author = authorship.get("author") if isinstance(authorship, dict) else None
                name = author.get("display_name") if isinstance(author, dict) else None
                if isinstance(name, str) and name.strip():
                    authors.append(name.strip())
            abstract = None
            inv = item.get("abstract_inverted_index")
            if isinstance(inv, dict):
                tokens = sorted(
                    ((pos, word) for word, positions in inv.items() for pos in (positions or [])),
                    key=lambda x: x[0],
                )
                abstract = " ".join(word for _, word in tokens)[:12000] or None
            year_value = item.get("publication_year")
            doi = item.get("doi")
            primary_location = item.get("primary_location") or {}
            url = primary_location.get("landing_page_url") or item.get("id")
            host_venue = item.get("host_venue") or {}
            source_meta = {
                "venue": host_venue.get("display_name"),
                "is_open_access": bool(
                    (item.get("open_access") or {}).get("is_oa")
                ),
            }
            try:
                candidates.append(
                    SourceCandidate(
                        source_api=self.provider_name,
                        external_source_id=work_id.rsplit("/", 1)[-1],
                        title=title,
                        authors=tuple(authors) if authors else None,
                        year=year_value if isinstance(year_value, int) else None,
                        doi=doi if isinstance(doi, str) else None,
                        url=url if isinstance(url, str) else None,
                        abstract=abstract,
                        citation_count=(
                            item.get("cited_by_count")
                            if isinstance(item.get("cited_by_count"), int)
                            else None
                        ),
                        source_meta=source_meta,
                    )
                )
            except ValueError:
                continue
        return candidates
