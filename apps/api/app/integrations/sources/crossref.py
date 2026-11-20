"""Crossref Works metadata adapter with conservative abstract reuse handling."""
from __future__ import annotations

import contextlib
import json
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

_BASE_URL = "https://api.crossref.org/works"
_SELECT = (
    "DOI,title,author,published,issued,published-print,published-online,"
    "URL,abstract,is-referenced-by-count,license,type,container-title"
)
_MAX_RESULTS = 1000
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_AUTHORS = 100
_MAX_TITLE_CHARS = 2000
_MAX_ABSTRACT_CHARS = 12_000
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_RETRY_BASE_SECONDS = 0.5
_RETRY_MAX_SECONDS = 8.0
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class _AbstractTextExtractor(HTMLParser):
    """Extract readable text from Crossref JATS/XML abstract fragments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return " ".join(self.parts).strip()


class CrossrefProvider:
    """Read-only Crossref Works API adapter."""

    provider_name = "crossref"

    def __init__(
        self,
        *,
        mailto: str = "",
        api_key: str = "",
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self._mailto = mailto.strip()
        self._api_key = api_key.strip()
        self._timeout = max(1.0, float(timeout_seconds))
        self._max_retries = max(0, int(max_retries))
        self._min_interval = max(0.0, min(float(min_interval_seconds), 30.0))

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        """Search bibliographic metadata; rows are capped at 1,000.

        Crossref has-license is not itself proof of Open Access. When the
        caller requests open_access_only, keep only records with explicit
        reusable CC BY, CC BY-SA, CC0 or public-domain licences.
        """
        if limit < 1:
            return []
        if not isinstance(query, str) or not query.strip():
            raise SourceProviderInvalidResponseError("Crossref query is empty")
        if len(query) > 500 or any(ord(char) < 32 for char in query):
            raise SourceProviderInvalidResponseError("Crossref query is invalid")
        if year is not None and (
            isinstance(year, bool)
            or not isinstance(year, int)
            or not 1000 <= year <= 2200
        ):
            raise SourceProviderInvalidResponseError("Invalid publication year")

        effective_limit = min(int(limit), _MAX_RESULTS)
        params = {
            "query.bibliographic": query.strip(),
            "rows": str(effective_limit),
            "select": _SELECT,
        }
        filters: list[str] = []
        if year is not None:
            filters.extend(
                [
                    f"from-pub-date:{year:04d}-01-01",
                    f"until-pub-date:{year:04d}-12-31",
                ]
            )
        if open_access_only:
            filters.append("has-license:1")
        if filters:
            params["filter"] = ",".join(filters)
        if self._mailto:
            params["mailto"] = self._mailto

        payload = self._request_json(params)
        if payload.get("status") == "error":
            message = payload.get("message")
            raise SourceProviderInvalidResponseError(
                "Crossref rejected the query: "
                f"{str(message or 'unknown API error')[:300]}"
            )
        message = payload.get("message")
        if not isinstance(message, dict):
            raise SourceProviderInvalidResponseError(
                "Crossref response is missing a message object"
            )
        items = message.get("items")
        if not isinstance(items, list):
            raise SourceProviderInvalidResponseError(
                "Crossref response is missing a works items array"
            )

        candidates: list[SourceCandidate] = []
        seen_dois: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            reusable_license = self._has_reusable_license(item.get("license"))
            if open_access_only and not reusable_license:
                continue
            candidate = self._to_candidate(item, allow_abstract=reusable_license)
            if candidate is None:
                continue
            identity = candidate.external_source_id.casefold()
            if identity in seen_dois:
                continue
            seen_dois.add(identity)
            candidates.append(candidate)
            if len(candidates) >= effective_limit:
                break
        return candidates

    def _request_json(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{_BASE_URL}?{urllib.parse.urlencode(params)}"
        for attempt in range(self._max_retries + 1):
            self._pace_requests()
            request = urllib.request.Request(url, method="GET")
            request.add_header("Accept", "application/json")
            user_agent = "ResearchAI/1.0 (Crossref Works metadata search)"
            if self._mailto:
                user_agent += f" (mailto:{self._mailto})"
            request.add_header("User-Agent", user_agent)
            if self._api_key:
                request.add_header("crossref-api-key", f"Bearer {self._api_key}")

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
                        "Crossref request timed out"
                    ) from None
                raise SourceProviderUnavailableError(
                    "Crossref transport error: "
                    f"{type(reason).__name__ if reason else type(exc).__name__}"
                ) from None
            except TimeoutError:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderTimeoutError(
                    "Crossref request timed out"
                ) from None
            except OSError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderUnavailableError(
                    f"Crossref transport error: {type(exc).__name__}"
                ) from None

            if len(raw) > _MAX_RESPONSE_BYTES:
                raise SourceProviderInvalidResponseError(
                    "Crossref response exceeded the configured size limit"
                )
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SourceProviderInvalidResponseError(
                    "Crossref returned invalid JSON"
                ) from None
            if not isinstance(payload, dict):
                raise SourceProviderInvalidResponseError(
                    "Crossref JSON response must be an object"
                )
            return payload

        raise SourceProviderUnavailableError("Crossref retries exhausted")

    def _pace_requests(self) -> None:
        """Serialize requests and pace them within this Python process."""
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
                f"Crossref authentication/access failed (status={status})"
            ) from None
        if status in _RETRYABLE_STATUSES:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            if status == 429:
                raise SourceProviderRateLimitError(
                    "Crossref rate limit exceeded"
                ) from None
            if status == 408:
                raise SourceProviderTimeoutError(
                    "Crossref request timed out"
                ) from None
            raise SourceProviderUnavailableError(
                f"Crossref provider error (status={status})"
            ) from None
        raise SourceProviderInvalidResponseError(
            f"Crossref returned unexpected HTTP status {status}"
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
        if not isinstance(value, list):
            return False
        for entry in value:
            if not isinstance(entry, dict):
                continue
            raw_url = entry.get("URL") or entry.get("url")
            if not isinstance(raw_url, str):
                continue
            parsed = urllib.parse.urlparse(raw_url.strip())
            host = (parsed.hostname or "").lower()
            segments = [part.lower() for part in parsed.path.split("/") if part]
            if segments and segments[0] == "licenses":
                segments = segments[1:]
            if host not in {"creativecommons.org", "www.creativecommons.org"}:
                continue
            if len(segments) == 2 and segments[0] in {"by", "by-sa"}:
                return True
            if segments[:2] in (
                ["publicdomain", "zero"],
                ["publicdomain", "mark"],
            ):
                return True
        return False

    @classmethod
    def _to_candidate(
        cls,
        item: dict[str, Any],
        *,
        allow_abstract: bool,
    ) -> SourceCandidate | None:
        doi = item.get("DOI")
        if not isinstance(doi, str) or not doi.strip():
            return None
        title = cls._first_text(item.get("title"))
        if not title:
            return None
        authors = cls._authors(item.get("author"))
        year = cls._publication_year(item)
        abstract = (
            cls._abstract_text(item.get("abstract"))
            if allow_abstract
            else None
        )
        citation_count = item.get("is-referenced-by-count")
        if isinstance(citation_count, bool) or not isinstance(citation_count, int):
            citation_count = None
        url = item.get("URL")
        if not isinstance(url, str) or not url.strip():
            url = f"https://doi.org/{urllib.parse.quote(doi.strip(), safe='')}"
        try:
            return SourceCandidate(
                source_api="crossref",
                external_source_id=doi.strip().lower(),
                title=title[:_MAX_TITLE_CHARS],
                authors=tuple(authors) if authors else None,
                year=year,
                doi=doi,
                url=url,
                abstract=abstract,
                citation_count=citation_count,
            )
        except ValueError:
            return None

    @staticmethod
    def _first_text(value: Any) -> str | None:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        return None

    @staticmethod
    def _authors(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for author in value[:_MAX_AUTHORS]:
            if not isinstance(author, dict):
                continue
            name = author.get("name")
            if not isinstance(name, str) or not name.strip():
                given = author.get("given")
                family = author.get("family")
                pieces = [
                    part.strip()
                    for part in (given, family)
                    if isinstance(part, str) and part.strip()
                ]
                name = " ".join(pieces)
            if isinstance(name, str) and name.strip():
                result.append(" ".join(name.split()))
        return result

    @staticmethod
    def _publication_year(item: dict[str, Any]) -> int | None:
        for field in ("published-print", "published-online", "issued", "created"):
            date = item.get(field)
            if not isinstance(date, dict):
                continue
            parts = date.get("date-parts")
            if not isinstance(parts, list) or not parts:
                continue
            first = parts[0]
            if not isinstance(first, list) or not first:
                continue
            year = first[0]
            if isinstance(year, int) and not isinstance(year, bool):
                return year
        return None

    @staticmethod
    def _abstract_text(value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        parser = _AbstractTextExtractor()
        try:
            parser.feed(value)
            parser.close()
        except Exception:
            return None
        text = parser.text()
        return text[:_MAX_ABSTRACT_CHARS] or None


__all__ = ["CrossrefProvider"]
