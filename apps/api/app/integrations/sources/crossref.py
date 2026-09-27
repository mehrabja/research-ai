from __future__ import annotations

import json
import urllib.parse
import urllib.request

from app.core.config import get_settings
from app.domain.source import SourceCandidate


class CrossrefProvider:
    provider_name = "crossref"

    def __init__(self) -> None:
        settings = get_settings()
        self._mailto = settings.crossref_mailto
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
            "query.bibliographic": query,
            "rows": str(max(1, min(limit, 100))),
        }
        if year is not None:
            params["filter"] = (
                f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
            )

        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "research-ai/1.0"
                + (f" mailto:{self._mailto}" if self._mailto else "")
            ),
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Crossref request failed: {type(exc).__name__}") from exc

        items = ((payload.get("message") or {}).get("items") or [])
        if not isinstance(items, list):
            return []

        candidates: list[SourceCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title_values = item.get("title") or []
            title = title_values[0] if title_values and isinstance(title_values[0], str) else None
            doi = item.get("DOI")
            if not title:
                continue

            authors: list[str] = []
            for author in item.get("author") or []:
                if not isinstance(author, dict):
                    continue
                name = " ".join(
                    x
                    for x in [author.get("given"), author.get("family")]
                    if isinstance(x, str) and x
                )
                if name:
                    authors.append(name)

            issued = (
                item.get("published-print")
                or item.get("published-online")
                or {}
            )
            date_parts = issued.get("date-parts") or [[]]
            year_value = date_parts[0][0] if date_parts and date_parts[0] else None
            url_value = item.get("URL")

            candidates.append(
                SourceCandidate(
                    source_api=self.provider_name,
                    external_source_id=str(doi or url_value or title)[:500],
                    title=title,
                    authors=tuple(authors) or None,
                    year=year_value if isinstance(year_value, int) else None,
                    doi=doi if isinstance(doi, str) else None,
                    url=url_value if isinstance(url_value, str) else None,
                    abstract=None,
                    citation_count=None,
                )
            )
        return candidates
