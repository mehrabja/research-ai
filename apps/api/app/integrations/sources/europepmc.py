"""Europe PMC literature discovery adapter.

The adapter returns bounded bibliographic metadata. Abstracts are included
only when the record declares an explicitly reusable licence; OA status alone
is not treated as permission to redistribute abstract text.
"""
from __future__ import annotations

import contextlib
import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)

_DEFAULT_BASE_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
)
_MAX_RESULTS = 100
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_AUTHORS = 100
_MAX_TITLE_CHARS = 2000
_MAX_ABSTRACT_CHARS = 12_000
_MAX_SOURCE_ID_CHARS = 100
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_RETRY_BASE_SECONDS = 0.5
_RETRY_MAX_SECONDS = 8.0
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0
_YEAR_RE = re.compile(r"^(?:19|20|21)\d{2}$")
_SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class _AbstractTextExtractor(HTMLParser):
    """Reduce provider-supplied abstract markup to bounded readable text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts).strip()


class EuropePMCProvider:
    """Read-only Europe PMC REST search adapter."""

    provider_name = "europepmc"

    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.34,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = max(1.0, float(timeout_seconds))
        self._max_retries = max(0, int(max_retries))
        self._min_interval = max(0.0, min(float(min_interval_seconds), 10.0))

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        """Search one bounded Europe PMC page (maximum 100 records)."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise SourceProviderInvalidResponseError("Invalid result limit")
        if not isinstance(query, str) or not query.strip():
            raise SourceProviderInvalidResponseError("Europe PMC query is empty")
        query_text = query.strip()
        if len(query_text) > 500 or any(ord(char) < 32 for char in query_text):
            raise SourceProviderInvalidResponseError("Europe PMC query is invalid")
        if year is not None and (
            isinstance(year, bool)
            or not isinstance(year, int)
            or not 1000 <= year <= 2200
        ):
            raise SourceProviderInvalidResponseError("Invalid publication year")

        query_parts = [f"({query_text})"]
        if year is not None:
            query_parts.append(f"PUB_YEAR:{year}")
        if open_access_only:
            query_parts.append("OPEN_ACCESS:Y")

        effective_limit = min(limit, _MAX_RESULTS)
        payload = self._request_json(
            {
                "query": " AND ".join(query_parts),
                "format": "json",
                "resultType": "core",
                "pageSize": str(effective_limit),
                "cursorMark": "*",
            }
        )
        if payload.get("errCode") or payload.get("errMsg"):
            raise SourceProviderInvalidResponseError(
                "Europe PMC rejected the search query"
            )

        result_list = payload.get("resultList")
        if not isinstance(result_list, dict):
            raise SourceProviderInvalidResponseError(
                "Europe PMC response is missing resultList"
            )
        records = result_list.get("result")
        if not isinstance(records, list):
            raise SourceProviderInvalidResponseError(
                "Europe PMC response is missing the result array"
            )

        candidates: list[SourceCandidate] = []
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                continue
            candidate = self._to_candidate(record)
            if candidate is None:
                continue
            identity = candidate.external_source_id.casefold()
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append(candidate)
            if len(candidates) >= effective_limit:
                break
        return candidates

    def _request_json(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
        for attempt in range(self._max_retries + 1):
            self._pace_requests()
            request = urllib.request.Request(url, method="GET")
            request.add_header("Accept", "application/json")
            request.add_header(
                "User-Agent",
                "ResearchAI/1.0 (read-only Europe PMC metadata discovery)",
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self._timeout
                ) as response:
                    raw = response.read(_MAX_RESPONSE_BYTES + 1)
            except urllib.error.HTTPError as exc:
                self._handle_http_error(exc, attempt)
                continue
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                if isinstance(reason, TimeoutError):
                    raise SourceProviderTimeoutError(
                        "Europe PMC request timed out"
                    ) from None
                raise SourceProviderUnavailableError(
                    "Europe PMC transport error: "
                    f"{type(reason).__name__ if reason else type(exc).__name__}"
                ) from None
            except TimeoutError:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderTimeoutError(
                    "Europe PMC request timed out"
                ) from None
            except OSError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderUnavailableError(
                    f"Europe PMC transport error: {type(exc).__name__}"
                ) from None

            if len(raw) > _MAX_RESPONSE_BYTES:
                raise SourceProviderInvalidResponseError(
                    "Europe PMC response exceeded the configured size limit"
                )
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SourceProviderInvalidResponseError(
                    "Europe PMC returned invalid JSON"
                ) from None
            if not isinstance(payload, dict):
                raise SourceProviderInvalidResponseError(
                    "Europe PMC JSON response must be an object"
                )
            return payload

        raise SourceProviderUnavailableError(
            "Europe PMC request retries exhausted"
        )

    def _pace_requests(self) -> None:
        """Serialize and pace requests within this Python process."""
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
                f"Europe PMC access failed (status={status})"
            ) from None
        if status in _RETRYABLE_STATUSES:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            if status == 429:
                raise SourceProviderRateLimitError(
                    "Europe PMC rate limit exceeded"
                ) from None
            if status == 408:
                raise SourceProviderTimeoutError(
                    "Europe PMC request timed out"
                ) from None
            raise SourceProviderUnavailableError(
                f"Europe PMC provider error (status={status})"
            ) from None
        raise SourceProviderInvalidResponseError(
            f"Europe PMC returned unexpected HTTP status {status}"
        ) from None

    @staticmethod
    def _parse_retry_after(exc: urllib.error.HTTPError) -> float | None:
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

    @staticmethod
    def _has_reusable_license(value: Any) -> bool:
        values = value if isinstance(value, list) else [value]
        for raw in values:
            if not isinstance(raw, str) or not raw.strip():
                continue
            license_text = " ".join(raw.strip().lower().replace("_", " ").split())
            if license_text in {
                "cc by",
                "cc by 3.0",
                "cc by 4.0",
                "cc by-sa",
                "cc by-sa 3.0",
                "cc by-sa 4.0",
                "cc0",
                "cc0 1.0",
                "public domain",
            }:
                return True
            parsed = urllib.parse.urlparse(raw.strip())
            host = (parsed.hostname or "").lower()
            segments = [part.lower() for part in parsed.path.split("/") if part]
            if host not in {"creativecommons.org", "www.creativecommons.org"}:
                continue
            if segments and segments[0] == "licenses":
                segments = segments[1:]
            if len(segments) >= 2 and segments[0] in {"by", "by-sa"}:
                version = segments[1]
                if re.fullmatch(r"\d+(?:\.\d+)?", version):
                    return True
            if segments[:2] in (
                ["publicdomain", "zero"],
                ["publicdomain", "mark"],
            ):
                return True
        return False

    @classmethod
    def _to_candidate(cls, item: dict[str, Any]) -> SourceCandidate | None:
        source = item.get("source")
        identifier = item.get("id")
        title = item.get("title")
        if (
            not isinstance(source, str)
            or not _SOURCE_RE.fullmatch(source.strip())
            or not isinstance(identifier, (str, int))
            or isinstance(identifier, bool)
            or not _ID_RE.fullmatch(str(identifier).strip())
            or not isinstance(title, str)
            or not title.strip()
        ):
            return None

        source = source.strip().upper()
        identifier = str(identifier).strip()
        authors = cls._authors(item.get("authorList"))
        year = cls._publication_year(item.get("pubYear"))
        doi = item.get("doi")
        if not isinstance(doi, str) or not doi.strip():
            doi = None

        abstract: str | None = None
        if cls._has_reusable_license(item.get("license")):
            abstract = cls._abstract_text(item.get("abstractText"))

        citation_count = item.get("citedByCount")
        if isinstance(citation_count, str) and citation_count.isdigit():
            citation_count = int(citation_count)
        if isinstance(citation_count, bool) or not isinstance(citation_count, int):
            citation_count = None

        article_url = (
            "https://europepmc.org/article/"
            f"{urllib.parse.quote(source, safe='')}/"
            f"{urllib.parse.quote(identifier, safe='')}"
        )
        try:
            return SourceCandidate(
                source_api="europepmc",
                external_source_id=f"{source}:{identifier}",
                title=" ".join(title.split())[:_MAX_TITLE_CHARS],
                authors=tuple(authors) if authors else None,
                year=year,
                doi=doi,
                url=article_url,
                abstract=abstract,
                citation_count=citation_count,
            )
        except ValueError:
            return None

    @staticmethod
    def _authors(value: Any) -> list[str]:
        if not isinstance(value, dict):
            return []
        authors = value.get("author")
        if not isinstance(authors, list):
            return []
        result: list[str] = []
        for author in authors[:_MAX_AUTHORS]:
            if not isinstance(author, dict):
                continue
            name = author.get("fullName") or author.get("collectiveName")
            if not isinstance(name, str) or not name.strip():
                first = author.get("firstName")
                last = author.get("lastName")
                parts = [
                    part.strip()
                    for part in (first, last)
                    if isinstance(part, str) and part.strip()
                ]
                name = " ".join(parts)
            if isinstance(name, str) and name.strip():
                result.append(" ".join(name.split()))
        return result

    @staticmethod
    def _publication_year(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        text = str(value).strip() if value is not None else ""
        if not _YEAR_RE.fullmatch(text):
            return None
        year = int(text)
        return year if 1000 <= year <= 2200 else None

    @staticmethod
    def _abstract_text(value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        parser = _AbstractTextExtractor()
        try:
            parser.feed(value)
            parser.close()
            cleaned = parser.text()
        except Exception:
            cleaned = html.unescape(re.sub(r"<[^>]*>", " ", value))
            cleaned = " ".join(cleaned.split())
        return cleaned[:_MAX_ABSTRACT_CHARS] or None


__all__ = ["EuropePMCProvider"]
