"""ClinicalTrials.gov API v2 read-only study discovery."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
import socket
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

_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
_MAX_RESULTS = 500
_PAGE_SIZE = 100
_MAX_PAGES = 5
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_SUMMARY_CHARS = 12_000
_MAX_LIST_ITEMS = 40
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_RETRY_BASE_SECONDS = 0.5
_RETRY_MAX_SECONDS = 8.0
_NCT_RE = re.compile(r"^NCT[0-9]{8}$")
_DATE_RE = re.compile(r"^([0-9]{4})(?:-[0-9]{2}(?:-[0-9]{2})?)?$")
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


def _clean_text(value: object, *, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(
        "".join(char if ord(char) >= 32 and ord(char) != 127 else " " for char in value).split()
    )
    return cleaned[:limit]


def _clean_string_list(value: object, *, limit: int = _MAX_LIST_ITEMS) -> list[str]:
    if not isinstance(value, list):
        return []
    results: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = _clean_text(item, limit=300)
        identity = cleaned.casefold()
        if cleaned and identity not in seen:
            seen.add(identity)
            results.append(cleaned)
        if len(results) >= limit:
            break
    return results


def _study_date_year(status_module: dict[str, Any]) -> int | None:
    first_post = status_module.get("studyFirstPostDateStruct")
    if not isinstance(first_post, dict):
        return None
    raw_date = first_post.get("date")
    if not isinstance(raw_date, str):
        return None
    match = _DATE_RE.fullmatch(raw_date.strip())
    if match is None:
        return None
    year = int(match.group(1))
    return year if 1000 <= year <= 2200 else None


class ClinicalTrialsGovProvider:
    """Search public study records; this adapter never submits or edits studies."""

    provider_name = "clinicaltrials"

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.5,
    ) -> None:
        self._timeout = max(1.0, min(float(timeout_seconds), 120.0))
        self._max_retries = max(0, min(int(max_retries), 10))
        self._min_interval = max(0.0, min(float(min_interval_seconds), 30.0))

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        """Search by free-text study term with bounded page-token traversal.

        ClinicalTrials.gov is a public study registry rather than a publication
        repository. Its records are publicly viewable, so the bibliographic
        open_access_only flag does not alter this provider's result set.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise SourceProviderInvalidResponseError("Invalid result limit")
        if not isinstance(query, str) or not query.strip():
            raise SourceProviderInvalidResponseError("ClinicalTrials.gov query is empty")
        query_text = query.strip()
        if len(query_text) > 500 or any(ord(char) < 32 or ord(char) == 127 for char in query_text):
            raise SourceProviderInvalidResponseError("ClinicalTrials.gov query is invalid")
        if year is not None and (
            isinstance(year, bool)
            or not isinstance(year, int)
            or not 1000 <= year <= 2200
        ):
            raise SourceProviderInvalidResponseError("Invalid study year")

        # The v2 API supports pageSize up to 1,000. Keep each response smaller
        # and cap the complete search to five pages / 500 records.
        effective_limit = min(limit, _MAX_RESULTS)
        candidates: list[SourceCandidate] = []
        seen_nct_ids: set[str] = set()
        page_token: str | None = None
        for _ in range(_MAX_PAGES):
            page_size = min(_PAGE_SIZE, effective_limit - len(candidates))
            if page_size <= 0:
                break
            params = {
                "query.term": query_text,
                "pageSize": str(page_size),
                "format": "json",
                "countTotal": "true",
                "sort": "LastUpdatePostDate:desc",
                "fields": "|".join(
                    (
                        "NCTId",
                        "BriefTitle",
                        "OfficialTitle",
                        "OverallStatus",
                        "StudyType",
                        "Phase",
                        "Condition",
                        "InterventionName",
                        "LeadSponsorName",
                        "StudyFirstPostDate",
                        "BriefSummary",
                    )
                ),
            }
            if year is not None:
                params["filter.advanced"] = f"AREA[StudyFirstPostDate]{year:04d}"
            if page_token:
                params["pageToken"] = page_token

            payload = self._request_json(params)
            records = payload.get("studies")
            if not isinstance(records, list):
                raise SourceProviderInvalidResponseError(
                    "ClinicalTrials.gov response is missing the studies array"
                )
            for record in records:
                if not isinstance(record, dict):
                    continue
                candidate = self._to_candidate(record)
                if candidate is None:
                    continue
                identity = candidate.external_source_id.casefold()
                if identity in seen_nct_ids:
                    continue
                seen_nct_ids.add(identity)
                candidates.append(candidate)
                if len(candidates) >= effective_limit:
                    break

            next_token = payload.get("nextPageToken")
            if next_token is not None and (
                not isinstance(next_token, str) or len(next_token) > 2048
            ):
                raise SourceProviderInvalidResponseError(
                    "ClinicalTrials.gov response contains an invalid page token"
                )
            if len(candidates) >= effective_limit or not records or not next_token:
                break
            if next_token == page_token:
                raise SourceProviderInvalidResponseError(
                    "ClinicalTrials.gov returned a repeated page token"
                )
            page_token = next_token

        return candidates

    @staticmethod
    def _to_candidate(record: dict[str, Any]) -> SourceCandidate | None:
        protocol = record.get("protocolSection")
        if not isinstance(protocol, dict):
            return None
        identification = protocol.get("identificationModule")
        if not isinstance(identification, dict):
            return None
        nct_id = identification.get("nctId")
        if not isinstance(nct_id, str) or _NCT_RE.fullmatch(nct_id) is None:
            return None
        title = _clean_text(
            identification.get("briefTitle") or identification.get("officialTitle"),
            limit=2000,
        )
        if not title:
            return None

        status_module = protocol.get("statusModule")
        if not isinstance(status_module, dict):
            status_module = {}
        design_module = protocol.get("designModule")
        if not isinstance(design_module, dict):
            design_module = {}
        conditions_module = protocol.get("conditionsModule")
        if not isinstance(conditions_module, dict):
            conditions_module = {}
        interventions_module = protocol.get("armsInterventionsModule")
        if not isinstance(interventions_module, dict):
            interventions_module = {}
        sponsor_module = protocol.get("sponsorCollaboratorsModule")
        if not isinstance(sponsor_module, dict):
            sponsor_module = {}
        description_module = protocol.get("descriptionModule")
        if not isinstance(description_module, dict):
            description_module = {}

        status = _clean_text(status_module.get("overallStatus"), limit=80)
        study_type = _clean_text(design_module.get("studyType"), limit=80)
        phases = _clean_string_list(design_module.get("phases"), limit=8)
        conditions = _clean_string_list(conditions_module.get("conditions"))
        intervention_names: list[str] = []
        raw_interventions = interventions_module.get("interventions")
        if isinstance(raw_interventions, list):
            for item in raw_interventions:
                if not isinstance(item, dict):
                    continue
                name = _clean_text(item.get("name"), limit=300)
                if name and name.casefold() not in {
                    value.casefold() for value in intervention_names
                }:
                    intervention_names.append(name)
                if len(intervention_names) >= _MAX_LIST_ITEMS:
                    break

        lead_sponsor: str | None = None
        lead = sponsor_module.get("leadSponsor")
        if isinstance(lead, dict):
            lead_sponsor = _clean_text(lead.get("name"), limit=300) or None

        first_post_date = ""
        first_post = status_module.get("studyFirstPostDateStruct")
        if isinstance(first_post, dict):
            first_post_date = _clean_text(first_post.get("date"), limit=40)

        summary = _clean_text(
            description_module.get("briefSummary"),
            limit=_MAX_SUMMARY_CHARS,
        )
        processed_date = datetime.now(UTC).date().isoformat()
        metadata_lines = [
            "Source: ClinicalTrials.gov (https://clinicaltrials.gov).",
            f"Processed by Research AI on: {processed_date} (UTC).",
            (
                "Transformation notice: Research AI normalizes selected registry "
                "fields into source metadata; consult the linked registry record "
                "for the authoritative current study record."
            ),
            f"ClinicalTrials.gov study: {nct_id}",
            f"Overall status: {status}" if status else "",
            f"Study type: {study_type}" if study_type else "",
            f"Phase: {', '.join(phases)}" if phases else "",
            f"Conditions: {', '.join(conditions)}" if conditions else "",
            f"Interventions: {', '.join(intervention_names)}" if intervention_names else "",
            f"Lead sponsor: {lead_sponsor}" if lead_sponsor else "",
            f"First posted: {first_post_date}" if first_post_date else "",
            f"Brief summary: {summary}" if summary else "",
        ]
        abstract = "\n".join(line for line in metadata_lines if line)[:_MAX_SUMMARY_CHARS]
        year = _study_date_year(status_module)

        return SourceCandidate(
            source_api=ClinicalTrialsGovProvider.provider_name,
            external_source_id=nct_id,
            title=title,
            year=year,
            url=f"https://clinicaltrials.gov/study/{nct_id}",
            abstract=abstract or None,
        )

    def _request_json(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{_BASE_URL}?{urllib.parse.urlencode(params)}"
        for attempt in range(self._max_retries + 1):
            self._pace_requests()
            request = urllib.request.Request(url, method="GET")
            request.add_header("Accept", "application/json")
            request.add_header(
                "User-Agent",
                "ResearchAI/1.0 (read-only ClinicalTrials.gov API v2 study discovery)",
            )
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    raw = response.read(_MAX_RESPONSE_BYTES + 1)
            except urllib.error.HTTPError as exc:
                status = exc.code
                if status in {401, 403}:
                    raise SourceProviderAuthError(
                        "ClinicalTrials.gov API access was denied"
                    ) from None
                if status == 429 or status in _RETRYABLE_STATUSES:
                    if attempt < self._max_retries:
                        retry_after = (
                            exc.headers.get("Retry-After")
                            if exc.headers is not None
                            else None
                        )
                        self._sleep_backoff(attempt, retry_after)
                        continue
                    if status == 429:
                        raise SourceProviderRateLimitError(
                            "ClinicalTrials.gov rate limit exceeded"
                        ) from None
                    if status == 408:
                        raise SourceProviderTimeoutError(
                            "ClinicalTrials.gov request timed out"
                        ) from None
                    if status >= 500:
                        raise SourceProviderUnavailableError(
                            f"ClinicalTrials.gov returned HTTP {status}"
                        ) from None
                if status == 408:
                    raise SourceProviderTimeoutError(
                        "ClinicalTrials.gov request timed out"
                    ) from None
                raise SourceProviderInvalidResponseError(
                    f"ClinicalTrials.gov rejected the request with HTTP {status}"
                ) from None
            except (TimeoutError, socket.timeout):
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderTimeoutError(
                    "ClinicalTrials.gov request timed out"
                ) from None
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                if isinstance(reason, (TimeoutError, socket.timeout)):
                    raise SourceProviderTimeoutError(
                        "ClinicalTrials.gov request timed out"
                    ) from None
                raise SourceProviderUnavailableError(
                    "ClinicalTrials.gov transport error"
                ) from None
            except OSError:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise SourceProviderUnavailableError(
                    "ClinicalTrials.gov transport error"
                ) from None

            if len(raw) > _MAX_RESPONSE_BYTES:
                raise SourceProviderInvalidResponseError(
                    "ClinicalTrials.gov response exceeded the configured size limit"
                )
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SourceProviderInvalidResponseError(
                    "ClinicalTrials.gov returned invalid JSON"
                ) from None
            if not isinstance(payload, dict):
                raise SourceProviderInvalidResponseError(
                    "ClinicalTrials.gov JSON response must be an object"
                )
            return payload

        raise SourceProviderUnavailableError(
            "ClinicalTrials.gov retries exhausted"
        )

    def _pace_requests(self) -> None:
        global _LAST_REQUEST_AT
        with _RATE_LOCK:
            now = time.monotonic()
            wait = self._min_interval - (now - _LAST_REQUEST_AT)
            if wait > 0:
                time.sleep(wait)
            _LAST_REQUEST_AT = time.monotonic()

    @staticmethod
    def _sleep_backoff(attempt: int, retry_after: str | None = None) -> None:
        delay = min(_RETRY_BASE_SECONDS * (2**attempt), _RETRY_MAX_SECONDS)
        if retry_after:
            try:
                delay = max(delay, min(float(retry_after), _RETRY_MAX_SECONDS))
            except ValueError:
                pass
        time.sleep(delay)

__all__ = ["ClinicalTrialsGovProvider"]
