from __future__ import annotations

import io
import json
import re
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest

from app.integrations.sources.base import (
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)
from app.integrations.sources.clinicaltrials import ClinicalTrialsGovProvider


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _provider(*, retries: int = 0) -> ClinicalTrialsGovProvider:
    return ClinicalTrialsGovProvider(
        timeout_seconds=5,
        max_retries=retries,
        min_interval_seconds=0,
    )


def _study(
    *,
    nct_id: str = "NCT01234567",
    title: str = "Study of a new intervention",
    status: str = "RECRUITING",
    phase: str = "PHASE2",
) -> dict:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct_id,
                "briefTitle": title,
                "officialTitle": "Official study title",
            },
            "statusModule": {
                "overallStatus": status,
                "studyFirstPostDateStruct": {"date": "2022-05-17"},
            },
            "designModule": {
                "studyType": "INTERVENTIONAL",
                "phases": [phase],
            },
            "conditionsModule": {"conditions": ["Condition A", "Condition B"]},
            "armsInterventionsModule": {
                "interventions": [{"name": "Intervention X"}]
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Sponsor Inc."}
            },
            "descriptionModule": {"briefSummary": "A bounded study summary."},
        }
    }


def _payload(studies: list[dict], *, next_page: str | None = None) -> bytes:
    body: dict = {"studies": studies, "totalCount": len(studies)}
    if next_page:
        body["nextPageToken"] = next_page
    return json.dumps(body).encode()


def _install(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.clinicaltrials.urllib.request.urlopen",
        handler,
    )


def _http_error(status: int, *, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError(
        "https://clinicaltrials.gov/api/v2/studies",
        status,
        f"HTTP {status}",
        headers,
        io.BytesIO(b""),
    )


def test_search_maps_study_metadata_to_source_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([_study()]))

    _install(monkeypatch, handler)
    results = _provider().search(query="condition A", limit=10)

    assert len(results) == 1
    candidate = results[0]
    assert candidate.source_api == "clinicaltrials"
    assert candidate.external_source_id == "NCT01234567"
    assert candidate.title == "Study of a new intervention"
    assert candidate.url == "https://clinicaltrials.gov/study/NCT01234567"
    assert candidate.year == 2022
    assert "Overall status: RECRUITING" in (candidate.abstract or "")
    assert "Phase: PHASE2" in (candidate.abstract or "")
    assert "Lead sponsor: Sponsor Inc." in (candidate.abstract or "")
    assert "Source: ClinicalTrials.gov (https://clinicaltrials.gov)." in (candidate.abstract or "")
    assert re.search(
        r"Processed by Research AI on: \d{4}-\d{2}-\d{2} \(UTC\)",
        candidate.abstract or "",
    )
    assert "Transformation notice:" in (candidate.abstract or "")

    params = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    assert params["query.term"] == ["condition A"]
    assert params["pageSize"] == ["10"]
    assert params["format"] == ["json"]
    assert params["sort"] == ["LastUpdatePostDate:desc"]
    assert params["filter.advanced"] == ["AREA[StudyFirstPostDate]2022"]
    assert params["fields"] == [
        "NCTId|BriefTitle|OfficialTitle|OverallStatus|StudyType|Phase|Condition|"
        "InterventionName|LeadSponsorName|StudyFirstPostDate|BriefSummary"
    ]


def test_search_follows_page_tokens_and_deduplicates_nct_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []
    pages = [
        _payload([_study(nct_id="NCT00000001"), _study(nct_id="NCT00000001")], next_page="page-2"),
        _payload([_study(nct_id="NCT00000002")]),
    ]

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(pages[len(requests) - 1])

    _install(monkeypatch, handler)
    results = _provider().search(query="condition", limit=3)

    assert [item.external_source_id for item in results] == [
        "NCT00000001",
        "NCT00000002",
    ]
    assert len(requests) == 2
    second_params = parse_qs(urlparse(requests[1].full_url).query)  # type: ignore[attr-defined]
    assert second_params["pageToken"] == ["page-2"]


def test_search_rejects_repeated_page_token(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = {"count": 0}

    def handler(request: object, timeout: float) -> _Response:
        requests["count"] += 1
        return _Response(_payload([_study(nct_id=f"NCT0000000{requests['count']}")], next_page="same"))

    _install(monkeypatch, handler)
    with pytest.raises(SourceProviderInvalidResponseError, match="repeated page token"):
        _provider().search(query="test", limit=250)
    assert requests["count"] == 2


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (429, SourceProviderRateLimitError),
        (408, SourceProviderTimeoutError),
        (500, SourceProviderUnavailableError),
        (400, SourceProviderInvalidResponseError),
    ],
)
def test_http_errors_are_mapped_to_typed_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    error_type: type[Exception],
) -> None:
    _install(
        monkeypatch,
        lambda request, timeout: (_ for _ in ()).throw(_http_error(status)),
    )
    with pytest.raises(error_type):
        _provider().search(query="test", limit=1)


def test_http_error_without_headers_can_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(request: object, timeout: float) -> _Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(
                "https://clinicaltrials.gov/api/v2/studies",
                500,
                "HTTP 500",
                None,
                io.BytesIO(b""),
            )
        return _Response(_payload([]))

    sleeps: list[float] = []
    _install(monkeypatch, handler)
    monkeypatch.setattr(
        "app.integrations.sources.clinicaltrials.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    _provider(retries=1).search(query="headers missing", limit=1)
    assert calls["count"] == 2
    assert sleeps == [0.5]


def test_retry_after_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def handler(request: object, timeout: float) -> _Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _http_error(429, retry_after="99")
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    monkeypatch.setattr(
        "app.integrations.sources.clinicaltrials.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    _provider(retries=1).search(query="retry", limit=1)
    assert calls["count"] == 2
    assert sleeps == [8.0]


@pytest.mark.parametrize("query,limit", [("", 1), ("  ", 1), ("x", 0), ("x", True)])
def test_search_rejects_invalid_inputs(query: str, limit: int) -> None:
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query=query, limit=limit)  # type: ignore[arg-type]


def test_invalid_json_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, lambda request, timeout: _Response(b"{bad json"))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="test", limit=1)
