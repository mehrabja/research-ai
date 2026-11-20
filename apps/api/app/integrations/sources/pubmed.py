"""PubMed discovery adapter over NCBI E-utilities.

The adapter returns concise bibliographic metadata only. Abstract/full-text
retrieval remains in the existing report-scoped document extraction pipeline.
"""
from __future__ import annotations

import contextlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)

_DEFAULT_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_RETRY_BASE_SECONDS = 0.5
_RETRY_MAX_SECONDS = 5.0
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s;,]+)", re.IGNORECASE)


class PubMedProvider:
    """NCBI PubMed source discovery adapter."""

    provider_name = "pubmed"

    def __init__(
        self,
        *,
        api_key: str = "",
        email: str = "",
        tool: str = "research_ai",
        base_url: str = _DEFAULT_BASE_URL,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.34,
    ) -> None:
        self._api_key = api_key.strip()
        self._email = email.strip()
        self._tool = tool.strip() or "research_ai"
        self._base_url = base_url.rstrip("/")
        self._timeout = max(1.0, float(timeout_seconds))
        self._max_retries = max(0, int(max_retries))
        self._min_interval = max(0.0, float(min_interval_seconds))

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        """Search PubMed and map ESummary records to normalized candidates."""
        if limit < 1:
            return []

        term = f"({query.strip()})"
        if year is not None:
            term += f" AND {year}[dp]"
        if open_access_only:
            term += " AND free full text[sb]"

        search_payload = self._request_json(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": str(min(limit, 1000)),
                "sort": "relevance",
            },
        )
        search_result = search_payload.get("esearchresult")
        if not isinstance(search_result, dict):
            raise SourceProviderInvalidResponseError(
                "PubMed ESearch response is missing esearchresult"
            )
        raw_ids = search_result.get("idlist")
        if not isinstance(raw_ids, list):
            raise SourceProviderInvalidResponseError(
                "PubMed ESearch response is missing idlist"
            )

        pmids = [
            str(value).strip()
            for value in raw_ids
            if isinstance(value, (str, int)) and str(value).strip()
        ][: min(limit, 1000)]
        if not pmids:
            return []

        summary_payload = self._request_json(
            "esummary.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
                "version": "2.0",
            },
        )
        result = summary_payload.get("result")
        if not isinstance(result, dict):
            raise SourceProviderInvalidResponseError(
                "PubMed ESummary response is missing result"
            )

        candidates: list[SourceCandidate] = []
        seen: set[str] = set()
        for pmid in pmids:
            record = result.get(pmid)
            if not isinstance(record, dict):
                continue
            candidate = self._to_candidate(pmid, record)
            if candidate is None or candidate.external_source_id in seen:
                continue
            seen.add(candidate.external_source_id)
            candidates.append(candidate)
            if len(candidates) >= limit:
                break
        return candidates

    def _request_json(
        self,
        endpoint: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        url = (
            f"{self._base_url}/{endpoint}?"
            f"{urllib.parse.urlencode(self._request_params(params))}"
        )
        for attempt in range(self._max_retries + 1):
            self._pace_requests()
            request = urllib.request.Request(url, method="GET")
            request.add_header("Accept", "application/json")
            request.add_header(
                "User-Agent",
                f"ResearchAI/1.0 (NCBI E-utilities; tool={self._tool})",
            )
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
                    "PubMed request timed out"
                ) from None
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                if isinstance(reason, TimeoutError):
                    raise SourceProviderTimeoutError(
                        "PubMed request timed out"
                    ) from None
                raise SourceProviderUnavailableError(
                    "PubMed transport error: "
                    f"{type(reason).__name__ if reason else type(exc).__name__}"
                ) from None
            except OSError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderUnavailableError(
                    f"PubMed transport error: {type(exc).__name__}"
                ) from None

            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SourceProviderInvalidResponseError(
                    "PubMed returned invalid JSON"
                ) from None
            if not isinstance(payload, dict):
                raise SourceProviderInvalidResponseError(
                    "PubMed JSON response must be an object"
                )
            error = payload.get("error")
            if error:
                message = str(error)
                if "rate limit" in message.lower():
                    raise SourceProviderRateLimitError(
                        "NCBI rate limit exceeded"
                    )
                raise SourceProviderInvalidResponseError(
                    "PubMed rejected the query"
                )
            return payload

        raise SourceProviderUnavailableError(
            "PubMed request retries exhausted"
        )

    def _request_params(self, params: dict[str, str]) -> dict[str, str]:
        result = {"tool": self._tool, **params}
        if self._email:
            result["email"] = self._email
        if self._api_key:
            result["api_key"] = self._api_key
        return result

    def _pace_requests(self) -> None:
        """Conservatively pace requests within this Python process."""
        global _LAST_REQUEST_AT
        if self._min_interval <= 0:
            return
        with _RATE_LOCK:
            now = time.monotonic()
            delay = self._min_interval - (now - _LAST_REQUEST_AT)
            if delay > 0:
                time.sleep(delay)
            _LAST_REQUEST_AT = time.monotonic()

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
                f"NCBI authentication failed (status={status})"
            ) from None
        if status == 429:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            raise SourceProviderRateLimitError(
                "NCBI rate limit exceeded"
            ) from None
        if 500 <= status < 600:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            raise SourceProviderUnavailableError(
                f"NCBI provider error (status={status})"
            ) from None
        raise SourceProviderInvalidResponseError(
            f"NCBI returned unexpected status {status}"
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
            seconds = float(str(raw).strip()) if raw is not None else None
        except (TypeError, ValueError):
            return None
        return seconds if seconds is not None and seconds >= 0 else None

    @staticmethod
    def _sleep_backoff(
        attempt: int,
        *,
        retry_after: float | None = None,
    ) -> None:
        delay = (
            min(retry_after, _RETRY_MAX_SECONDS)
            if retry_after is not None
            else min(_RETRY_BASE_SECONDS * (2**attempt), _RETRY_MAX_SECONDS)
        )
        if delay > 0:
            time.sleep(delay)

    @classmethod
    def _to_candidate(
        cls,
        pmid: str,
        record: dict[str, Any],
    ) -> SourceCandidate | None:
        title = record.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        authors_raw = record.get("authors")
        authors: tuple[str, ...] | None = None
        if isinstance(authors_raw, list):
            author_names = [
                value.strip()
                for author in authors_raw
                if isinstance(author, dict)
                and isinstance((value := author.get("name")), str)
                and value.strip()
            ]
            authors = tuple(author_names) or None

        doi = cls._extract_doi(record)
        pubdate = record.get("pubdate") or record.get("sortpubdate")
        year = None
        if isinstance(pubdate, str):
            match = _YEAR_RE.search(pubdate)
            if match:
                year = int(match.group(1))

        return SourceCandidate(
            source_api="pubmed",
            external_source_id=pmid,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            abstract=None,
            citation_count=None,
        )

    @staticmethod
    def _extract_doi(record: dict[str, Any]) -> str | None:
        article_ids = record.get("articleids")
        if isinstance(article_ids, list):
            for item in article_ids:
                if not isinstance(item, dict):
                    continue
                if str(item.get("idtype", "")).lower() == "doi":
                    value = item.get("value")
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        elocation = record.get("elocationid")
        if isinstance(elocation, str):
            match = _DOI_RE.search(elocation)
            if match:
                return match.group(1)
        return None


__all__ = ["PubMedProvider"]
