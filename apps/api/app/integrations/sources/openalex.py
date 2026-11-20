"""OpenAlex works-search adapter with bounded paging and licensed abstracts.

Only bibliographic metadata is returned. Abstract inverted indexes are
reconstructed only when OpenAlex exposes an explicitly reusable license.
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

_BASE_URL = "https://api.openalex.org"
_FIELDS = (
    "id,doi,title,publication_year,authorships,primary_location,"
    "best_oa_location,open_access,cited_by_count,abstract_inverted_index"
)
_RETRY_BASE_SECONDS = 0.5
_RETRY_MAX_SECONDS = 5.0
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_ABSTRACT_POSITIONS = 20_000
_MAX_ABSTRACT_CHARS = 12_000
_MAX_AUTHORS = 100
_MAX_LIMIT = 1000
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_OPEN_LICENSES = frozenset({"cc-by", "cc-by-sa", "cc0", "public-domain", "pd"})
_WORK_ID_RE = re.compile(r"W[0-9]+", re.IGNORECASE)
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class OpenAlexProvider:
    """OpenAlex works search using its standard REST list endpoint."""

    provider_name = "openalex"

    def __init__(
        self,
        *,
        api_key: str = "",
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.15,
    ) -> None:
        self._api_key = api_key.strip()
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
        """Search up to 1,000 results with ordinary page-based pagination.

        A free key is optional for these bounded basic searches. Cursor paging
        is intentionally not used because it is unnecessary for the current
        search limit and requires an authenticated OpenAlex key after page 1.
        """
        if limit < 1:
            return []
        if not isinstance(query, str) or not query.strip():
            raise SourceProviderInvalidResponseError("OpenAlex query is empty")

        effective_limit = min(int(limit), _MAX_LIMIT)
        per_page = min(effective_limit, 100)
        filters: list[str] = []
        if year is not None:
            if isinstance(year, bool) or not isinstance(year, int):
                raise SourceProviderInvalidResponseError("Invalid publication year")
            filters.append(f"publication_year:{year}")
        if open_access_only:
            filters.append("open_access.is_oa:true")

        candidates: list[SourceCandidate] = []
        seen_ids: set[str] = set()
        page = 1

        while len(candidates) < effective_limit:
            params = {
                "search": query.strip(),
                "per_page": str(per_page),
                "page": str(page),
                "select": _FIELDS,
            }
            if filters:
                params["filter"] = ",".join(filters)

            payload = self._request_json(params)
            results = payload.get("results")
            if not isinstance(results, list):
                raise SourceProviderInvalidResponseError(
                    "OpenAlex response is missing a results array"
                )
            if not results:
                break

            for row in results:
                if not isinstance(row, dict):
                    continue
                candidate = self._to_candidate(row)
                if candidate is None:
                    continue
                if candidate.external_source_id in seen_ids:
                    continue
                seen_ids.add(candidate.external_source_id)
                candidates.append(candidate)
                if len(candidates) >= effective_limit:
                    break

            if len(results) < per_page:
                break
            page += 1

        return candidates[:effective_limit]

    def _request_json(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{_BASE_URL}/works?{urllib.parse.urlencode(params)}"
        for attempt in range(self._max_retries + 1):
            self._pace_requests()
            request = urllib.request.Request(url, method="GET")
            request.add_header("Accept", "application/json")
            request.add_header(
                "User-Agent", "ResearchAI/1.0 (OpenAlex works search)"
            )
            if self._api_key:
                # Keep credentials out of URLs, application access logs and traces.
                request.add_header("Authorization", f"Bearer {self._api_key}")

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
                        "OpenAlex request timed out"
                    ) from None
                raise SourceProviderUnavailableError(
                    "OpenAlex transport error: "
                    f"{type(reason).__name__ if reason else type(exc).__name__}"
                ) from None
            except TimeoutError:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderTimeoutError(
                    "OpenAlex request timed out"
                ) from None
            except OSError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderUnavailableError(
                    f"OpenAlex transport error: {type(exc).__name__}"
                ) from None

            if len(raw) > _MAX_RESPONSE_BYTES:
                raise SourceProviderInvalidResponseError(
                    "OpenAlex response exceeded the configured size limit"
                )
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SourceProviderInvalidResponseError(
                    "OpenAlex returned invalid JSON"
                ) from None
            if not isinstance(payload, dict):
                raise SourceProviderInvalidResponseError(
                    "OpenAlex JSON response must be an object"
                )
            return payload

        raise SourceProviderUnavailableError("OpenAlex retries exhausted")

    def _pace_requests(self) -> None:
        """Pace requests conservatively within this Python process."""
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
                f"OpenAlex authentication/access failed (status={status})"
            ) from None
        if status == 429:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            raise SourceProviderRateLimitError(
                "OpenAlex rate limit or daily budget exceeded"
            ) from None
        if status in _RETRYABLE_STATUSES:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            raise SourceProviderUnavailableError(
                f"OpenAlex provider error (status={status})"
            ) from None
        raise SourceProviderInvalidResponseError(
            f"OpenAlex returned unexpected status {status}"
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

    @classmethod
    def _to_candidate(cls, record: dict[str, Any]) -> SourceCandidate | None:
        external_id = cls._work_id(record.get("id"))
        title = record.get("title") or record.get("display_name")
        if external_id is None or not isinstance(title, str) or not title.strip():
            return None

        authorships = record.get("authorships")
        author_names: list[str] = []
        if isinstance(authorships, list):
            for authorship in authorships[:_MAX_AUTHORS]:
                if not isinstance(authorship, dict):
                    continue
                author = authorship.get("author")
                if not isinstance(author, dict):
                    continue
                name = author.get("display_name")
                if isinstance(name, str) and name.strip():
                    author_names.append(name.strip())

        primary_location = record.get("primary_location")
        best_oa_location = record.get("best_oa_location")
        primary_location = (
            primary_location if isinstance(primary_location, dict) else {}
        )
        best_oa_location = (
            best_oa_location if isinstance(best_oa_location, dict) else {}
        )
        landing_page = primary_location.get("landing_page_url")
        if not isinstance(landing_page, str) or not landing_page.strip():
            landing_page = record.get("id")

        year = record.get("publication_year")
        if isinstance(year, bool) or not isinstance(year, int):
            year = None
        citation_count = record.get("cited_by_count")
        if isinstance(citation_count, bool) or not isinstance(citation_count, int):
            citation_count = None

        open_license = (
            best_oa_location.get("license") or primary_location.get("license")
        )
        abstract = cls._licensed_abstract(
            record.get("abstract_inverted_index"), open_license
        )
        doi = record.get("doi")
        if not isinstance(doi, str):
            doi = None

        try:
            return SourceCandidate(
                source_api="openalex",
                external_source_id=external_id,
                title=title,
                authors=tuple(author_names) if author_names else None,
                year=year,
                doi=doi,
                url=landing_page if isinstance(landing_page, str) else None,
                abstract=abstract,
                citation_count=citation_count,
            )
        except ValueError:
            return None

    @staticmethod
    def _work_id(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        parsed = urllib.parse.urlparse(value.strip())
        if parsed.scheme != "https" or parsed.netloc.lower() not in {
            "openalex.org",
            "www.openalex.org",
        }:
            return None
        work_id = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        return work_id.upper() if _WORK_ID_RE.fullmatch(work_id) else None

    @staticmethod
    def _licensed_abstract(
        inverted_index: Any,
        license_value: Any,
    ) -> str | None:
        if not isinstance(inverted_index, dict) or not inverted_index:
            return None
        license_name = (
            license_value.strip().lower()
            if isinstance(license_value, str)
            else ""
        )
        if license_name not in _OPEN_LICENSES:
            return None

        positions: dict[int, str] = {}
        for word, indexes in inverted_index.items():
            if not isinstance(word, str) or not isinstance(indexes, list):
                continue
            for index in indexes:
                if (
                    isinstance(index, int)
                    and not isinstance(index, bool)
                    and 0 <= index < _MAX_ABSTRACT_POSITIONS
                ):
                    positions.setdefault(index, word)
        if not positions:
            return None
        words = [positions.get(index, "") for index in range(max(positions) + 1)]
        abstract = " ".join(words).strip()
        return abstract[:_MAX_ABSTRACT_CHARS] or None


__all__ = ["OpenAlexProvider"]
