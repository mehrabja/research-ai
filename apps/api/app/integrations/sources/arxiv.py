"""arXiv Atom API adapter for report-scoped scientific discovery."""
from __future__ import annotations

import contextlib
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)

_BASE_URL = "https://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
_RETRY_BASE_SECONDS = 1.0
_RETRY_MAX_SECONDS = 10.0
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_RESULTS = 100
_MAX_AUTHORS = 100
_MAX_TITLE_CHARS = 1200
_MAX_ABSTRACT_CHARS = 12_000
_NEW_ID = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$")
_OLD_ID = re.compile(r"^[a-z][a-z0-9.-]*(?:\.[a-z0-9.-]+)?/\d{7}(?:v\d+)?$", re.I)
_VERSION = re.compile(r"v\d+$", re.I)
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class ArxivProvider:
    """Read-only arXiv API adapter. No credentials or third-party SDK required."""

    provider_name = "arxiv"

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        min_interval_seconds: float = 3.0,
    ) -> None:
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
        """Search arXiv using one bounded Atom request.

        arXiv papers are hosted as open preprints; the provider therefore has
        no separate open-access filter. The abstract is returned as metadata
        supplied by the Atom API, while PDF download/extraction stays in the
        existing controlled ingestion workflow.
        """
        if limit < 1:
            return []
        if not isinstance(query, str) or not query.strip():
            raise SourceProviderInvalidResponseError("arXiv query is empty")
        if len(query) > 500 or any(ord(char) < 32 for char in query):
            raise SourceProviderInvalidResponseError("arXiv query is invalid")
        if year is not None and (
            isinstance(year, bool)
            or not isinstance(year, int)
            or not 1900 <= year <= 2100
        ):
            raise SourceProviderInvalidResponseError("Invalid publication year")

        query_parts = [f"all:{query.strip()}"]
        if year is not None:
            query_parts.append(
                f"submittedDate:[{year}01010000 TO {year}12312359]"
            )
        search_query = " AND ".join(
            f"({part})" if len(query_parts) > 1 else part
            for part in query_parts
        )
        max_results = min(int(limit), _MAX_RESULTS)
        params = {
            "search_query": search_query,
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        root = self._request_feed(params)
        entries = root.findall(f"{_ATOM}entry")
        candidates: list[SourceCandidate] = []
        seen_ids: set[str] = set()
        for entry in entries:
            candidate = self._to_candidate(entry)
            if candidate is None or candidate.external_source_id in seen_ids:
                continue
            seen_ids.add(candidate.external_source_id)
            candidates.append(candidate)
            if len(candidates) >= max_results:
                break
        return candidates

    def _request_feed(self, params: dict[str, str]) -> ET.Element:
        url = f"{_BASE_URL}?{urllib.parse.urlencode(params)}"
        for attempt in range(self._max_retries + 1):
            self._pace_requests()
            request = urllib.request.Request(url, method="GET")
            request.add_header("Accept", "application/atom+xml, application/xml")
            request.add_header(
                "User-Agent", "ResearchAI/1.0 (read-only arXiv metadata discovery)"
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
                        "arXiv request timed out"
                    ) from None
                raise SourceProviderUnavailableError(
                    "arXiv transport error: "
                    f"{type(reason).__name__ if reason else type(exc).__name__}"
                ) from None
            except TimeoutError:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderTimeoutError(
                    "arXiv request timed out"
                ) from None
            except OSError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderUnavailableError(
                    f"arXiv transport error: {type(exc).__name__}"
                ) from None

            if len(raw) > _MAX_RESPONSE_BYTES:
                raise SourceProviderInvalidResponseError(
                    "arXiv response exceeded the configured size limit"
                )
            # ElementTree does not resolve external entities, and rejecting DTDs
            # also avoids entity-expansion payloads from untrusted upstream data.
            upper = raw[:4096].upper()
            if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
                raise SourceProviderInvalidResponseError(
                    "arXiv XML must not contain DTD/entity declarations"
                )
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                raise SourceProviderInvalidResponseError(
                    "arXiv returned invalid Atom XML"
                ) from None
            if root.tag != f"{_ATOM}feed":
                raise SourceProviderInvalidResponseError(
                    "arXiv response is not an Atom feed"
                )
            self._raise_feed_error(root)
            return root

        raise SourceProviderUnavailableError("arXiv retries exhausted")

    @staticmethod
    def _raise_feed_error(root: ET.Element) -> None:
        entries = root.findall(f"{_ATOM}entry")
        if len(entries) != 1:
            return
        entry_id = _child_text(entries[0], f"{_ATOM}id")
        if entry_id and "/api/errors" in entry_id:
            message = _child_text(entries[0], f"{_ATOM}summary")
            raise SourceProviderInvalidResponseError(
                f"arXiv query was rejected: {(message or 'unknown API error')[:300]}"
            )

    def _pace_requests(self) -> None:
        """Enforce the recommended delay within this Python process."""
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
        retry_after = _retry_after(exc)
        with contextlib.suppress(Exception):
            exc.read()
        if status in (401, 403):
            raise SourceProviderAuthError(
                f"arXiv access failed (status={status})"
            ) from None
        if status == 429:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            raise SourceProviderRateLimitError(
                "arXiv rate limit exceeded"
            ) from None
        if status in {408, 500, 502, 503, 504}:
            if attempt < self._max_retries:
                self._sleep_backoff(attempt, retry_after=retry_after)
                return
            if status == 408:
                raise SourceProviderTimeoutError(
                    "arXiv request timed out"
                ) from None
            raise SourceProviderUnavailableError(
                f"arXiv provider error (status={status})"
            ) from None
        raise SourceProviderInvalidResponseError(
            f"arXiv returned unexpected HTTP status {status}"
        ) from None

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
    def _to_candidate(cls, entry: ET.Element) -> SourceCandidate | None:
        raw_id = _child_text(entry, f"{_ATOM}id")
        paper_id = _parse_arxiv_id(raw_id)
        if paper_id is None:
            return None
        base_id, versioned_id = paper_id
        title = _collapse(_child_text(entry, f"{_ATOM}title"))
        if not title:
            return None
        abstract_text = _collapse(_child_text(entry, f"{_ATOM}summary"))
        abstract_value = abstract_text[:_MAX_ABSTRACT_CHARS] or None

        authors: list[str] = []
        for author in entry.findall(f"{_ATOM}author")[:_MAX_AUTHORS]:
            name = _collapse(_child_text(author, f"{_ATOM}name"))
            if name:
                authors.append(name)

        published = _child_text(entry, f"{_ATOM}published") or ""
        year_match = re.match(r"^(\d{4})-", published)
        year = int(year_match.group(1)) if year_match else None
        doi = _collapse(_child_text(entry, f"{_ARXIV}doi")) or None
        url_id = urllib.parse.quote(versioned_id, safe="./")
        try:
            return SourceCandidate(
                source_api="arxiv",
                external_source_id=base_id,
                title=title[:_MAX_TITLE_CHARS],
                authors=tuple(authors) if authors else None,
                year=year,
                doi=doi,
                url=f"https://arxiv.org/abs/{url_id}",
                abstract=abstract_value,
                citation_count=None,
            )
        except ValueError:
            return None


def _child_text(parent: ET.Element, tag: str) -> str | None:
    child = parent.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _collapse(value: str | None) -> str:
    return " ".join((value or "").split())


def _parse_arxiv_id(raw: str | None) -> tuple[str, str] | None:
    if not isinstance(raw, str):
        return None
    parsed = urllib.parse.urlparse(raw.strip())
    if parsed.scheme not in {"https", "http"} or parsed.netloc.lower() not in {
        "arxiv.org",
        "www.arxiv.org",
    }:
        return None
    if not parsed.path.startswith("/abs/"):
        return None
    versioned = urllib.parse.unquote(parsed.path[len("/abs/"):]).strip()
    if versioned.lower().endswith(".pdf"):
        versioned = versioned[:-4]
    base = _VERSION.sub("", versioned)
    if not (_NEW_ID.fullmatch(versioned) or _OLD_ID.fullmatch(versioned)):
        return None
    return base, versioned


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
        seconds = float(str(raw).strip()) if raw is not None else None
    except (TypeError, ValueError):
        return None
    return seconds if seconds is not None and seconds >= 0 else None


__all__ = ["ArxivProvider"]
