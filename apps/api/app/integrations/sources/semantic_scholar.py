"""Semantic Scholar source discovery adapter.

Uses the standard library ``urllib.request`` so that no new runtime
dependency is added to ``pyproject.toml``. The provider is synchronous,
matches the rest of the integration layer, and never logs secrets.
"""
from __future__ import annotations

import contextlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)

_FIELDS = (
    "paperId,title,authors,year,externalIds,url,abstract,"
    "citationCount,openAccessPdf"
)

_RETRY_BASE_SECONDS = 0.5
_RETRY_MAX_SECONDS = 5.0


class SemanticScholarProvider:
    """Semantic Scholar Graph API adapter."""

    provider_name = "semantic_scholar"

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._timeout = float(timeout_seconds)
        self._max_retries = max(0, int(max_retries))

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        params: dict[str, str] = {
            "query": query,
            "limit": str(limit),
            "fields": _FIELDS,
        }
        if year is not None:
            params["year"] = str(year)

        url = (
            f"{self._base_url}/paper/search?"
            f"{urllib.parse.urlencode(params)}"
        )

        payload = self._request_json(url)

        data = payload.get("data")
        if data is None:
            data = []
        if not isinstance(data, list):
            raise SourceProviderInvalidResponseError(
                "expected 'data' to be a list"
            )

        candidates: list[SourceCandidate] = []
        for paper in data:
            if not isinstance(paper, dict):
                continue
            if open_access_only and not paper.get("openAccessPdf"):
                continue
            candidate = self._to_candidate(paper)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def _request_json(self, url: str) -> dict:
        for attempt in range(self._max_retries + 1):
            request = urllib.request.Request(url, method="GET")
            request.add_header("Accept", "application/json")
            if self._api_key:
                request.add_header("x-api-key", self._api_key)

            try:
                with urllib.request.urlopen(
                    request, timeout=self._timeout
                ) as response:
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                self._handle_http_error(exc, attempt)
                continue
            except TimeoutError:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderTimeoutError(
                    "provider request timed out"
                ) from None
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                is_timeout = isinstance(reason, TimeoutError)
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                if is_timeout:
                    raise SourceProviderTimeoutError(
                        "provider request timed out"
                    ) from None
                raise SourceProviderUnavailableError(
                    "network error: "
                    f"{type(reason).__name__ if reason else type(exc).__name__}"
                ) from None
            except OSError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderUnavailableError(
                    f"network error: {type(exc).__name__}"
                ) from None

            try:
                decoded = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SourceProviderInvalidResponseError(
                    "invalid JSON body"
                ) from None
            if not isinstance(decoded, dict):
                raise SourceProviderInvalidResponseError(
                    "expected JSON object at top level"
                )
            return decoded

        raise SourceProviderUnavailableError("retries exhausted")

    def _handle_http_error(
        self,
        exc: urllib.error.HTTPError,
        attempt: int,
    ) -> None:
        status = exc.code
        retry_after = self._parse_retry_after(exc)

        with contextlib.suppress(Exception):
            exc.read()

        if status in (401, 403):
            raise SourceProviderAuthError(
                f"authentication failed (status={status})"
            ) from None

        if status == 429:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return None
            raise SourceProviderRateLimitError(
                f"rate limited (status={status})"
            ) from None

        if 500 <= status < 600:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt)
                return None
            raise SourceProviderUnavailableError(
                f"provider error (status={status})"
            ) from None

        raise SourceProviderInvalidResponseError(
            f"unexpected status {status}"
        ) from None

    @staticmethod
    def _parse_retry_after(
        exc: urllib.error.HTTPError,
    ) -> float | None:
        headers = getattr(exc, "headers", None)
        if headers is None:
            return None
        try:
            raw = headers.get("Retry-After")
        except Exception:
            return None
        if raw is None:
            return None
        try:
            seconds = float(str(raw).strip())
        except (ValueError, TypeError):
            return None
        if seconds < 0:
            return None
        return seconds

    @staticmethod
    def _sleep_backoff(
        attempt: int,
        retry_after: float | None = None,
    ) -> None:
        if retry_after is not None:
            delay = min(retry_after, _RETRY_MAX_SECONDS)
        else:
            delay = min(
                _RETRY_BASE_SECONDS * (2 ** attempt),
                _RETRY_MAX_SECONDS,
            )
        if delay > 0:
            time.sleep(delay)

    @staticmethod
    def _to_candidate(paper: dict) -> SourceCandidate | None:
        paper_id = paper.get("paperId")
        if not isinstance(paper_id, str) or not paper_id.strip():
            return None

        title = paper.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        external_ids = paper.get("externalIds") or {}
        doi = None
        if isinstance(external_ids, dict):
            raw_doi = external_ids.get("DOI")
            if isinstance(raw_doi, str):
                doi = raw_doi

        url = paper.get("url")
        if not isinstance(url, str) or not url.strip():
            url = None

        authors_raw = paper.get("authors") or []
        authors: tuple[str, ...] | None = None
        if isinstance(authors_raw, list):
            names: list[str] = []
            for entry in authors_raw:
                if isinstance(entry, dict):
                    name = entry.get("name")
                    if isinstance(name, str) and name.strip():
                        names.append(name.strip())
            if names:
                authors = tuple(names)

        abstract = paper.get("abstract")
        if not isinstance(abstract, str) or not abstract.strip():
            abstract = None

        year = paper.get("year")
        if not isinstance(year, int):
            year = None

        citation_count = paper.get("citationCount")
        if not isinstance(citation_count, int):
            citation_count = None

        try:
            return SourceCandidate(
                source_api="semantic_scholar",
                external_source_id=paper_id.strip(),
                title=title,
                authors=authors,
                year=year,
                doi=doi,
                url=url,
                abstract=abstract,
                citation_count=citation_count,
            )
        except ValueError:
            return None


__all__ = ["SemanticScholarProvider"]
