from __future__ import annotations

import io
import json
import urllib.error
from collections.abc import Callable

import pytest

from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderUnavailableError,
)
from app.integrations.sources.pubmed import PubMedProvider


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://eutils.ncbi.nlm.nih.gov/",
        code=status,
        msg=f"HTTP {status}",
        hdrs={},
        fp=io.BytesIO(b""),
    )


def _provider(*, retries: int = 0, api_key: str = "") -> PubMedProvider:
    return PubMedProvider(
        api_key=api_key,
        email="research@example.org",
        tool="research_ai_tests",
        timeout_seconds=5,
        max_retries=retries,
        min_interval_seconds=0,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[object, float], _Response],
) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.pubmed.urllib.request.urlopen",
        handler,
    )


def _search_payload(ids: list[str]) -> bytes:
    return json.dumps(
        {"esearchresult": {"count": str(len(ids)), "idlist": ids}}
    ).encode()


def _summary_payload(
    records: dict[str, dict[str, object]],
) -> bytes:
    return json.dumps({"result": {"uids": list(records), **records}}).encode()


def test_search_maps_pubmed_summary_to_source_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    responses = iter(
        [
            _search_payload(["12345678"]),
            _summary_payload(
                {
                    "12345678": {
                        "uid": "12345678",
                        "title": "A PubMed research article",
                        "pubdate": "2024 Mar",
                        "authors": [{"name": "Alice Example"}, {"name": "Bob Example"}],
                        "articleids": [
                            {"idtype": "pubmed", "value": "12345678"},
                            {"idtype": "doi", "value": "10.1234/EXAMPLE"},
                        ],
                        "fulljournalname": "Journal of Research",
                    }
                }
            ),
        ]
    )

    def handler(request: object, timeout: float) -> _Response:
        calls.append(request.full_url)  # type: ignore[attr-defined]
        return _Response(next(responses))

    _install(monkeypatch, handler)
    candidates = _provider().search(query="cancer immunotherapy", limit=10, year=2024)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_api == "pubmed"
    assert candidate.external_source_id == "12345678"
    assert candidate.title == "A PubMed research article"
    assert candidate.authors == ("Alice Example", "Bob Example")
    assert candidate.year == 2024
    assert candidate.doi == "10.1234/example"
    assert candidate.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert candidate.abstract is None
    assert len(calls) == 2
    assert "db=pubmed" in calls[0]
    assert "2024%5Bdp%5D" in calls[0]


def test_search_adds_free_full_text_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []

    def handler(request: object, timeout: float) -> _Response:
        urls.append(request.full_url)  # type: ignore[attr-defined]
        return _Response(_search_payload([]))

    _install(monkeypatch, handler)
    assert _provider().search(
        query="stroke rehabilitation",
        limit=5,
        open_access_only=True,
    ) == []
    assert "free+full+text%5Bsb%5D" in urls[0]


def test_search_empty_results_do_not_call_esummary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: object, timeout: float) -> _Response:
        calls.append(request.full_url)  # type: ignore[attr-defined]
        return _Response(_search_payload([]))

    _install(monkeypatch, handler)
    assert _provider().search(query="no matching article", limit=5) == []
    assert len(calls) == 1


def test_ncbi_tool_email_and_api_key_are_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_search_payload([]))

    _install(monkeypatch, handler)
    _provider(api_key="ncbi-test-key").search(query="x", limit=1)
    url = requests[0].full_url  # type: ignore[attr-defined]
    assert "tool=research_ai_tests" in url
    assert "email=research%40example.org" in url
    assert "api_key=ncbi-test-key" in url


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, SourceProviderAuthError),
        (403, SourceProviderAuthError),
        (429, SourceProviderRateLimitError),
        (500, SourceProviderUnavailableError),
        (503, SourceProviderUnavailableError),
        (400, SourceProviderInvalidResponseError),
    ],
)
def test_http_errors_are_typed(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    error_type: type[Exception],
) -> None:
    _install(
        monkeypatch,
        lambda request, timeout: (_ for _ in ()).throw(_http_error(status)),
    )
    with pytest.raises(error_type):
        _provider().search(query="x", limit=1)


def test_invalid_json_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, lambda request, timeout: _Response(b"{not-json"))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1)


def test_missing_summary_title_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            _search_payload(["1"]),
            _summary_payload({"1": {"uid": "1", "title": ""}}),
        ]
    )
    _install(
        monkeypatch,
        lambda request, timeout: _Response(next(responses)),
    )
    assert _provider().search(query="x", limit=1) == []
