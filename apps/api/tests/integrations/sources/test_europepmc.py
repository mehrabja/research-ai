from __future__ import annotations

import io
import json
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest

from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)
from app.integrations.sources.europepmc import EuropePMCProvider


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _provider(*, retries: int = 0, base_url: str | None = None) -> EuropePMCProvider:
    return EuropePMCProvider(
        base_url=base_url or "https://europepmc.example/search",
        timeout_seconds=5,
        max_retries=retries,
        min_interval_seconds=0,
    )


def _record(
    *,
    source: str = "MED",
    identifier: str = "37412345",
    license: str | None = "CC BY 4.0",
    abstract: str = "<p>Evidence <i>supports</i> the conclusion.</p>",
    **overrides: object,
) -> dict[str, object]:
    record: dict[str, object] = {
        "source": source,
        "id": identifier,
        "title": " A Europe PMC research article ",
        "authorList": {
            "author": [
                {"fullName": "Ada Lovelace"},
                {"firstName": "Alan", "lastName": "Turing"},
            ]
        },
        "pubYear": "2023",
        "doi": "10.1234/europepmc",
        "abstractText": abstract,
        "license": license,
        "citedByCount": 17,
        "isOpenAccess": "Y",
    }
    record.update(overrides)
    return record


def _payload(records: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {"hitCount": len(records), "resultList": {"result": records}}
    ).encode()


def _http_error(
    status: int,
    *,
    retry_after: str | None = None,
) -> urllib.error.HTTPError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError(
        "https://europepmc.example/search",
        status,
        f"HTTP {status}",
        headers,
        io.BytesIO(b""),
    )


def _install(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.europepmc.urllib.request.urlopen",
        handler,
    )


def test_search_maps_metadata_and_reusable_abstract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        assert timeout == 5
        return _Response(_payload([_record()]))

    _install(monkeypatch, handler)
    results = _provider().search(
        query="evidence synthesis", limit=20, year=2023
    )

    assert len(results) == 1
    candidate = results[0]
    assert candidate.source_api == "europepmc"
    assert candidate.external_source_id == "MED:37412345"
    assert candidate.title == "A Europe PMC research article"
    assert candidate.authors == ("Ada Lovelace", "Alan Turing")
    assert candidate.year == 2023
    assert candidate.doi == "10.1234/europepmc"
    assert candidate.url == "https://europepmc.org/article/MED/37412345"
    assert candidate.abstract == "Evidence supports the conclusion."
    assert candidate.citation_count == 17

    request = requests[0]
    params = parse_qs(urlparse(request.full_url).query)  # type: ignore[attr-defined]
    assert params["query"] == ["(evidence synthesis) AND PUB_YEAR:2023"]
    assert params["format"] == ["json"]
    assert params["resultType"] == ["core"]
    assert params["pageSize"] == ["20"]
    assert params["cursorMark"] == ["*"]
    assert request.get_header("Accept") == "application/json"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "license_value",
    [
        "CC BY",
        "CC BY 4.0",
        "CC BY-SA 4.0",
        "CC0",
        "https://creativecommons.org/licenses/by/4.0/",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    ],
)
def test_known_reusable_licences_allow_abstract(license_value: str) -> None:
    assert EuropePMCProvider._has_reusable_license(license_value)


@pytest.mark.parametrize(
    "license_value",
    [
        None,
        "",
        "unknown",
        "CC BY-NC",
        "CC BY-NC 4.0",
        "CC BY-ND 4.0",
        "CC BY-NC-ND",
        "https://creativecommons.org/licenses/by-nc/4.0/",
        "https://publisher.example/license",
    ],
)
def test_unknown_or_restricted_licences_do_not_allow_abstract(
    license_value: str | None,
) -> None:
    assert not EuropePMCProvider._has_reusable_license(license_value)


def test_abstract_is_omitted_without_reusable_licence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        lambda request, timeout: _Response(
            _payload([_record(license="CC BY-NC-ND 4.0")])
        ),
    )
    result = _provider().search(query="license", limit=1)
    assert len(result) == 1
    assert result[0].abstract is None


def test_open_access_filter_is_explicit_and_not_a_reuse_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(
            _payload([_record(license="CC BY-NC 4.0")])
        )

    _install(monkeypatch, handler)
    results = _provider().search(
        query="open access", limit=5, open_access_only=True
    )
    params = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    assert params["query"] == ["(open access) AND OPEN_ACCESS:Y"]
    assert results[0].abstract is None


def test_deduplication_and_invalid_records_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        _record(identifier="1"),
        _record(identifier="1"),
        _record(identifier="2", source="PMC"),
        {"source": "MED", "id": "3", "title": ""},
    ]
    _install(monkeypatch, lambda request, timeout: _Response(_payload(records)))
    results = _provider().search(query="deduplicate", limit=10)
    assert [row.external_source_id for row in results] == [
        "MED:1",
        "PMC:2",
    ]


def test_provider_uses_bounded_100_record_pages_for_large_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    _provider().search(query="bounded", limit=1000)
    params = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    assert params["pageSize"] == ["100"]


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, SourceProviderAuthError),
        (403, SourceProviderAuthError),
        (429, SourceProviderRateLimitError),
        (500, SourceProviderUnavailableError),
        (503, SourceProviderUnavailableError),
        (408, SourceProviderTimeoutError),
        (400, SourceProviderInvalidResponseError),
    ],
)
def test_search_follows_cursor_and_combines_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []
    pages = [
        {
            "resultList": {"result": [_record(identifier="1")]},
            "nextCursorMark": "cursor-2",
        },
        {
            "resultList": {"result": [_record(identifier="2")]},
            "nextCursorMark": "cursor-2",
        },
    ]

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(json.dumps(pages[len(requests) - 1]).encode())

    _install(monkeypatch, handler)
    results = _provider().search(query="cursor test", limit=150)

    assert [item.external_source_id for item in results] == [
        "MED:1",
        "MED:2",
    ]
    assert len(requests) == 2
    first = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    second = parse_qs(urlparse(requests[1].full_url).query)  # type: ignore[attr-defined]
    assert first["cursorMark"] == ["*"]
    assert second["cursorMark"] == ["cursor-2"]
    assert first["pageSize"] == ["100"]
    assert second["pageSize"] == ["100"]
    assert first["query"] == second["query"]


def test_search_stops_at_ten_pages_even_when_cursor_keeps_advancing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        page = len(requests)
        return _Response(
            json.dumps(
                {
                    "resultList": {
                        "result": [_record(identifier=str(page))]
                    },
                    "nextCursorMark": f"cursor-{page + 1}",
                }
            ).encode()
        )

    _install(monkeypatch, handler)
    results = _provider().search(query="page cap", limit=1000)
    assert len(results) == 10
    assert len(requests) == 10


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
        _provider().search(query="status", limit=1)


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
        "app.integrations.sources.europepmc.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    _provider(retries=1).search(query="retry", limit=1)
    assert calls["count"] == 2
    assert sleeps == [8.0]


def test_invalid_json_shape_and_response_size_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, lambda request, timeout: _Response(b"not-json"))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="bad json", limit=1)

    invalid = json.dumps({"resultList": {"result": "not-an-array"}}).encode()
    _install(monkeypatch, lambda request, timeout: _Response(invalid))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="bad shape", limit=1)

    monkeypatch.setattr(
        "app.integrations.sources.europepmc._MAX_RESPONSE_BYTES", 2
    )
    _install(monkeypatch, lambda request, timeout: _Response(b'{"ok":true}'))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="too large", limit=1)


def test_query_validation_and_custom_base_url() -> None:
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query=" ", limit=1)
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="bad", limit=True)  # type: ignore[arg-type]
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="bad", limit=1, year=True)  # type: ignore[arg-type]

    provider = _provider(base_url="https://custom.example/rest/search/")
    assert provider._base_url == "https://custom.example/rest/search"


def test_empty_search_is_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        lambda request, timeout: _Response(
            b'{"resultList":{"result":[]}}'
        ),
    )
    assert _provider().search(query="no matching records", limit=10) == []
