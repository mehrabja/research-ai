from __future__ import annotations

import io
import json
import urllib.error
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

import pytest

from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderUnavailableError,
)
from app.integrations.sources.openalex import OpenAlexProvider


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _http_error(
    status: int,
    *,
    retry_after: str | None = None,
) -> urllib.error.HTTPError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError(
        url="https://api.openalex.org/works",
        code=status,
        msg=f"HTTP {status}",
        hdrs=headers,
        fp=io.BytesIO(b""),
    )


def _provider(
    *,
    retries: int = 0,
    api_key: str = "",
) -> OpenAlexProvider:
    return OpenAlexProvider(
        api_key=api_key,
        timeout_seconds=5,
        max_retries=retries,
        min_interval_seconds=0,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[object, float], _Response],
) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.openalex.urllib.request.urlopen",
        handler,
    )


def _payload(results: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {"meta": {"count": len(results)}, "results": results}
    ).encode()


def _work(
    work_id: str = "W123",
    **overrides: object,
) -> dict[str, object]:
    result: dict[str, object] = {
        "id": f"https://openalex.org/{work_id}",
        "doi": "https://doi.org/10.1234/EXAMPLE",
        "title": "An OpenAlex research article",
        "publication_year": 2024,
        "authorships": [
            {"author": {"display_name": "Alice Example"}},
            {"author": {"display_name": "Bob Example"}},
        ],
        "primary_location": {
            "landing_page_url": "https://publisher.example/article",
            "license": "cc-by",
        },
        "best_oa_location": {"license": "cc-by"},
        "open_access": {"is_oa": True},
        "cited_by_count": 17,
        "abstract_inverted_index": {
            "Evidence": [0],
            "supports": [1],
            "the": [2],
            "claim.": [3],
        },
    }
    result.update(overrides)
    return result


def test_search_maps_work_and_reconstructs_cc_by_abstract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([_work()]))

    _install(monkeypatch, handler)
    candidates = _provider().search(
        query="evidence synthesis", limit=10, year=2024
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_api == "openalex"
    assert candidate.external_source_id == "W123"
    assert candidate.title == "An OpenAlex research article"
    assert candidate.authors == ("Alice Example", "Bob Example")
    assert candidate.year == 2024
    assert candidate.doi == "10.1234/example"
    assert candidate.url == "https://publisher.example/article"
    assert candidate.abstract == "Evidence supports the claim."
    assert candidate.citation_count == 17
    url = requests[0].full_url  # type: ignore[attr-defined]
    assert "search=evidence+synthesis" in url
    assert "publication_year%3A2024" in url
    assert "per_page=10" in url


def test_open_access_filter_is_applied_server_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []

    def handler(request: object, timeout: float) -> _Response:
        urls.append(request.full_url)  # type: ignore[attr-defined]
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    assert _provider().search(
        query="open access", limit=5, open_access_only=True
    ) == []
    assert "open_access.is_oa%3Atrue" in urls[0]


def test_unlicensed_abstract_is_not_reconstructed_even_when_open_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _work(
        best_oa_location={"license": None},
        primary_location={
            "landing_page_url": "https://publisher.example/article",
            "license": None,
        },
    )
    _install(
        monkeypatch,
        lambda request, timeout: _Response(_payload([record])),
    )

    result = _provider().search(query="license", limit=1)
    assert len(result) == 1
    assert result[0].abstract is None


def test_search_uses_multiple_bounded_pages_without_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: object, timeout: float) -> _Response:
        url = request.full_url  # type: ignore[attr-defined]
        calls.append(url)
        page = int(parse_qs(urlparse(url).query)["page"][0])
        start = (page - 1) * 100
        end = min(start + 100, 250)
        return _Response(
            _payload([_work(f"W{index}") for index in range(start + 1, end + 1)])
        )

    _install(monkeypatch, handler)
    results = _provider().search(query="large query", limit=250)

    assert len(results) == 250
    assert len(calls) == 3
    assert "page=1" in calls[0] and "per_page=100" in calls[0]
    assert "page=3" in calls[2]


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
def test_http_failures_are_typed(
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


def test_api_key_is_sent_as_bearer_header_not_query_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    _provider(api_key="openalex-test-key").search(query="x", limit=1)
    request = requests[0]
    assert request.get_header("Authorization") == "Bearer openalex-test-key"  # type: ignore[attr-defined]
    assert "openalex-test-key" not in request.full_url  # type: ignore[attr-defined]


def test_retry_after_is_respected_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def handler(request: object, timeout: float) -> _Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _http_error(429, retry_after="99")
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    monkeypatch.setattr(
        "app.integrations.sources.openalex.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    _provider(retries=1).search(query="retry", limit=1)
    assert calls["count"] == 2
    assert sleeps == [5.0]


def test_invalid_json_and_invalid_results_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, lambda request, timeout: _Response(b"not-json"))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1)

    _install(
        monkeypatch,
        lambda request, timeout: _Response(
            json.dumps({"results": "bad"}).encode()
        ),
    )
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1)


def test_no_api_key_is_supported_for_bounded_basic_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    _provider().search(query="basic", limit=1)
    assert requests[0].get_header("Authorization") is None  # type: ignore[attr-defined]
