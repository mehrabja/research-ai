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
    SourceProviderUnavailableError,
)
from app.integrations.sources.crossref import CrossrefProvider


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _provider(
    *,
    mailto: str = "",
    api_key: str = "",
    retries: int = 0,
) -> CrossrefProvider:
    return CrossrefProvider(
        mailto=mailto,
        api_key=api_key,
        timeout_seconds=5,
        max_retries=retries,
        min_interval_seconds=0,
    )


def _work(
    *,
    doi: str = "10.1234/example",
    abstract: str = "<jats:p>Supported <jats:italic>research</jats:italic> abstract.</jats:p>",
    licenses: list[dict[str, str]] | None = None,
    **overrides: object,
) -> dict[str, object]:
    item: dict[str, object] = {
        "DOI": doi,
        "title": ["A Crossref research article"],
        "author": [
            {"given": "Ada", "family": "Lovelace"},
            {"name": "Alan Turing"},
        ],
        "published-print": {"date-parts": [[2023, 9, 1]]},
        "published-online": {"date-parts": [[2022, 12, 1]]},
        "URL": "https://publisher.example/article",
        "abstract": abstract,
        "is-referenced-by-count": 31,
        "license": licenses if licenses is not None else [
            {
                "URL": "https://creativecommons.org/licenses/by/4.0/",
                "start": {"date-parts": [[2023, 1, 1]]},
                "content-version": "vor",
            }
        ],
        "type": "journal-article",
        "container-title": ["Journal of Research"],
    }
    item.update(overrides)
    return item


def _payload(items: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {
            "status": "ok",
            "message-type": "work-list",
            "message": {"total-results": len(items), "items": items},
        }
    ).encode()


def _http_error(
    status: int,
    *,
    retry_after: str | None = None,
) -> urllib.error.HTTPError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError(
        "https://api.crossref.org/works",
        status,
        f"HTTP {status}",
        headers,
        io.BytesIO(b""),
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    handler,
) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.crossref.urllib.request.urlopen",
        handler,
    )


def test_search_maps_crossref_metadata_and_reusable_abstract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([_work()]))

    _install(monkeypatch, handler)
    results = _provider(mailto="maintainer@example.org").search(
        query="evidence synthesis", limit=20, year=2023
    )

    assert len(results) == 1
    candidate = results[0]
    assert candidate.source_api == "crossref"
    assert candidate.external_source_id == "10.1234/example"
    assert candidate.doi == "10.1234/example"
    assert candidate.title == "A Crossref research article"
    assert candidate.authors == ("Ada Lovelace", "Alan Turing")
    assert candidate.year == 2023
    assert candidate.url == "https://publisher.example/article"
    assert candidate.abstract == "Supported research abstract."
    assert candidate.citation_count == 31

    params = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    assert params["query.bibliographic"] == ["evidence synthesis"]
    assert params["rows"] == ["20"]
    assert params["mailto"] == ["maintainer@example.org"]
    assert params["filter"] == [
        "from-pub-date:2023-01-01,until-pub-date:2023-12-31"
    ]
    assert "DOI" in params["select"][0]
    assert "api.crossref.org/works" in requests[0].full_url  # type: ignore[attr-defined]


def test_abstract_is_omitted_without_an_explicit_reusable_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _work(
        licenses=[
            {
                "URL": "https://creativecommons.org/licenses/by-nc/4.0/",
                "start": {"date-parts": [[2023, 1, 1]]},
            }
        ]
    )
    _install(
        monkeypatch,
        lambda request, timeout: _Response(_payload([record])),
    )
    results = _provider().search(query="license", limit=1)

    assert len(results) == 1
    assert results[0].abstract is None


def test_open_access_filter_requires_an_explicit_reusable_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        _work(
            doi="10.1234/not-reusable",
            licenses=[
                {"URL": "https://creativecommons.org/licenses/by-nc/4.0/"}
            ],
        ),
        _work(doi="10.1234/reusable"),
    ]
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload(records))

    _install(monkeypatch, handler)
    results = _provider().search(
        query="license", limit=10, open_access_only=True
    )

    assert [item.doi for item in results] == ["10.1234/reusable"]
    params = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    assert params["filter"] == ["has-license:1"]


def test_reusable_license_classification_is_conservative() -> None:
    assert CrossrefProvider._has_reusable_license(
        [{"URL": "https://creativecommons.org/licenses/by/4.0/"}]
    )
    assert CrossrefProvider._has_reusable_license(
        [{"URL": "https://creativecommons.org/licenses/by-sa/4.0/"}]
    )
    assert CrossrefProvider._has_reusable_license(
        [{"URL": "https://creativecommons.org/publicdomain/zero/1.0/"}]
    )
    assert not CrossrefProvider._has_reusable_license(
        [{"URL": "https://creativecommons.org/licenses/by-nc/4.0/"}]
    )
    assert not CrossrefProvider._has_reusable_license(
        [{"URL": "https://publisher.example/license"}]
    )


def test_api_key_uses_crossref_header_and_not_query_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    _provider(api_key="crossref-private-key").search(query="test", limit=1)

    request = requests[0]
    assert request.get_header("Crossref-api-key") == "Bearer crossref-private-key"  # type: ignore[attr-defined]
    assert "crossref-private-key" not in request.full_url  # type: ignore[attr-defined]


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
        _provider().search(query="test", limit=1)


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
        "app.integrations.sources.crossref.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    _provider(retries=1).search(query="retry", limit=1)
    assert calls["count"] == 2
    assert sleeps == [8.0]


def test_invalid_json_and_invalid_message_shapes_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, lambda request, timeout: _Response(b"not-json"))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="test", limit=1)

    invalid = json.dumps({"status": "ok", "message": {"items": "invalid"}}).encode()
    _install(monkeypatch, lambda request, timeout: _Response(invalid))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="test", limit=1)


def test_http_200_error_envelope_is_not_treated_as_an_empty_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = json.dumps({"status": "error", "message": "Invalid query"}).encode()
    _install(monkeypatch, lambda request, timeout: _Response(error))
    with pytest.raises(SourceProviderInvalidResponseError, match="Invalid query"):
        _provider().search(query="invalid", limit=1)


def test_query_validation_and_result_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query=" ", limit=1)
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1, year=True)

    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_payload([]))

    _install(monkeypatch, handler)
    _provider().search(query="large", limit=5000)
    params = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    assert params["rows"] == ["1000"]
