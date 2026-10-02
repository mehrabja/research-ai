"""Semantic Scholar provider tests. No live HTTP is performed."""
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
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)
from app.integrations.sources.semantic_scholar import (
    SemanticScholarProvider,
)


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _http_error(
    status: int, *, retry_after: str | None = None
) -> urllib.error.HTTPError:
    headers: dict[str, str] = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        url="https://api.semanticscholar.org/",
        code=status,
        msg=f"HTTP {status}",
        hdrs=headers,
        fp=io.BytesIO(b""),
    )


def _provider(*, max_retries: int = 0, api_key: str = "k") -> (
    SemanticScholarProvider
):
    return SemanticScholarProvider(
        api_key=api_key,
        base_url="https://api.semanticscholar.org/graph/v1",
        timeout_seconds=5.0,
        max_retries=max_retries,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[object, float], _Resp],
) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.semantic_scholar"
        ".urllib.request.urlopen",
        handler,
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.semantic_scholar.time.sleep",
        lambda _s: None,
    )


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------
def test_search_success(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(
        {
            "data": [
                {
                    "paperId": "P1",
                    "title": "T1",
                    "authors": [{"name": "A"}, {"name": "B"}],
                    "year": 2020,
                    "externalIds": {"DOI": "10.1/XYZ"},
                    "url": "https://example.org/p1",
                    "abstract": "abs",
                    "citationCount": 42,
                    "openAccessPdf": {"url": "https://x/y"},
                }
            ]
        }
    ).encode()
    _install(monkeypatch, lambda req, timeout: _Resp(body))
    out = _provider().search(query="x", limit=5)
    assert len(out) == 1
    c = out[0]
    assert c.external_source_id == "P1"
    assert c.title == "T1"
    assert c.authors == ("A", "B")
    assert c.year == 2020
    assert c.doi == "10.1/xyz"
    assert c.url == "https://example.org/p1"
    assert c.citation_count == 42
    assert c.source_api == "semantic_scholar"


def test_search_empty_data(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"data": []}).encode()
    _install(monkeypatch, lambda req, timeout: _Resp(body))
    assert _provider().search(query="x", limit=5) == []


def test_search_skips_malformed_papers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps(
        {
            "data": [
                {"paperId": "", "title": "T"},
                {"paperId": "P1", "title": ""},
                {"paperId": "P2", "title": "Ok"},
            ]
        }
    ).encode()
    _install(monkeypatch, lambda req, timeout: _Resp(body))
    out = _provider().search(query="x", limit=5)
    assert [c.external_source_id for c in out] == ["P2"]


def test_open_access_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(
        {
            "data": [
                {
                    "paperId": "P1",
                    "title": "T1",
                    "openAccessPdf": {"url": "https://x/y"},
                },
                {"paperId": "P2", "title": "T2"},
            ]
        }
    ).encode()
    _install(monkeypatch, lambda req, timeout: _Resp(body))
    out = _provider().search(query="x", limit=5, open_access_only=True)
    assert [c.external_source_id for c in out] == ["P1"]


def test_url_contains_query_limit_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []
    body = json.dumps({"data": []}).encode()

    def _handler(req: object, timeout: float) -> _Resp:
        calls.append(req)
        return _Resp(body)

    _install(monkeypatch, _handler)
    _provider().search(query="hi there", limit=7, year=2021)
    url = calls[0].full_url  # type: ignore[attr-defined]
    assert "query=hi+there" in url
    assert "limit=7" in url
    assert "year=2021" in url


def test_api_key_header_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    body = json.dumps({"data": []}).encode()

    def _handler(req: object, timeout: float) -> _Resp:
        calls.append(req)
        return _Resp(body)

    _install(monkeypatch, _handler)
    _provider(api_key="secret").search(query="x", limit=1)
    assert calls[0].get_header("X-api-key") == "secret"  # type: ignore[attr-defined]


def test_api_key_omitted_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []
    body = json.dumps({"data": []}).encode()

    def _handler(req: object, timeout: float) -> _Resp:
        calls.append(req)
        return _Resp(body)

    _install(monkeypatch, _handler)
    _provider(api_key="").search(query="x", limit=1)
    assert calls[0].get_header("X-api-key") is None  # type: ignore[attr-defined]


def test_search_paginates_to_requested_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    payloads = iter([
        {
            "total": 4,
            "next": 2,
            "data": [
                {"paperId": "P1", "title": "T1"},
                {"paperId": "P2", "title": "T2"},
            ],
        },
        {
            "total": 4,
            "next": None,
            "data": [
                {"paperId": "P3", "title": "T3"},
                {"paperId": "P4", "title": "T4"},
            ],
        },
    ])

    def _handler(req: object, timeout: float) -> _Resp:
        calls.append(req.full_url)  # type: ignore[attr-defined]
        return _Resp(json.dumps(next(payloads)).encode())

    _install(monkeypatch, _handler)
    out = _provider().search(query="x", limit=3)
    assert [c.external_source_id for c in out] == ["P1", "P2", "P3"]
    assert "offset=0" in calls[0]
    assert "offset=2" in calls[1]


def test_open_access_filter_fetches_additional_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = iter([
        {
            "total": 4,
            "next": 2,
            "data": [
                {"paperId": "P1", "title": "T1"},
                {"paperId": "P2", "title": "T2"},
            ],
        },
        {
            "total": 4,
            "next": None,
            "data": [
                {
                    "paperId": "P3",
                    "title": "T3",
                    "openAccessPdf": {"url": "https://x/p3"},
                },
                {
                    "paperId": "P4",
                    "title": "T4",
                    "openAccessPdf": {"url": "https://x/p4"},
                },
            ],
        },
    ])

    def _handler(req: object, timeout: float) -> _Resp:
        return _Resp(json.dumps(next(payloads)).encode())

    _install(monkeypatch, _handler)
    out = _provider().search(
        query="x", limit=2, open_access_only=True
    )
    assert [c.external_source_id for c in out] == ["P3", "P4"]


# ---------------------------------------------------------------------------
# HTTP classification
# ---------------------------------------------------------------------------
def test_401_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(_http_error(401)),
    )
    with pytest.raises(SourceProviderAuthError):
        _provider().search(query="x", limit=1)


def test_403_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(_http_error(403)),
    )
    with pytest.raises(SourceProviderAuthError):
        _provider().search(query="x", limit=1)


def test_429_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(_http_error(429)),
    )
    with pytest.raises(SourceProviderRateLimitError):
        _provider(max_retries=0).search(query="x", limit=1)


def test_500_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(_http_error(500)),
    )
    with pytest.raises(SourceProviderUnavailableError):
        _provider(max_retries=0).search(query="x", limit=1)


def test_503_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(_http_error(503)),
    )
    with pytest.raises(SourceProviderUnavailableError):
        _provider(max_retries=0).search(query="x", limit=1)


def test_400_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(_http_error(400)),
    )
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1)


# ---------------------------------------------------------------------------
# Transport classification
# ---------------------------------------------------------------------------
def test_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(TimeoutError()),
    )
    with pytest.raises(SourceProviderTimeoutError):
        _provider(max_retries=0).search(query="x", limit=1)


def test_urlerror_connection_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    err = urllib.error.URLError("connection refused")
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(err),
    )
    with pytest.raises(SourceProviderUnavailableError):
        _provider(max_retries=0).search(query="x", limit=1)


def test_urlerror_with_timeout_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    err = urllib.error.URLError(TimeoutError())
    _install(
        monkeypatch,
        lambda req, timeout: (_ for _ in ()).throw(err),
    )
    with pytest.raises(SourceProviderTimeoutError):
        _provider(max_retries=0).search(query="x", limit=1)


# ---------------------------------------------------------------------------
# Malformed body
# ---------------------------------------------------------------------------
def test_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, lambda req, timeout: _Resp(b"not-json"))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1)


def test_non_object_top_level(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps([1, 2, 3]).encode()
    _install(monkeypatch, lambda req, timeout: _Resp(body))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1)


def test_data_not_list(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"data": "nope"}).encode()
    _install(monkeypatch, lambda req, timeout: _Resp(body))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="x", limit=1)


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------
def test_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"n": 0}
    body = json.dumps(
        {"data": [{"paperId": "P1", "title": "T1"}]}
    ).encode()

    def _handler(req: object, timeout: float) -> _Resp:
        state["n"] += 1
        if state["n"] == 1:
            raise _http_error(500)
        return _Resp(body)

    _install(monkeypatch, _handler)
    out = _provider(max_retries=1).search(query="x", limit=1)
    assert state["n"] == 2
    assert len(out) == 1


def test_retry_exhausted_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"n": 0}

    def _handler(req: object, timeout: float) -> _Resp:
        state["n"] += 1
        raise _http_error(503)

    _install(monkeypatch, _handler)
    with pytest.raises(SourceProviderUnavailableError):
        _provider(max_retries=2).search(query="x", limit=1)
    assert state["n"] == 3


def test_retry_after_header_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"n": 0}
    slept: list[float] = []
    body = json.dumps({"data": []}).encode()

    def _handler(req: object, timeout: float) -> _Resp:
        state["n"] += 1
        if state["n"] == 1:
            raise _http_error(429, retry_after="2")
        return _Resp(body)

    _install(monkeypatch, _handler)
    monkeypatch.setattr(
        "app.integrations.sources.semantic_scholar.time.sleep",
        lambda s: slept.append(s),
    )
    _provider(max_retries=1).search(query="x", limit=1)
    assert slept == [2.0]


def test_retry_after_bounded_by_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"n": 0}
    slept: list[float] = []
    body = json.dumps({"data": []}).encode()

    def _handler(req: object, timeout: float) -> _Resp:
        state["n"] += 1
        if state["n"] == 1:
            raise _http_error(429, retry_after="99999")
        return _Resp(body)

    _install(monkeypatch, _handler)
    monkeypatch.setattr(
        "app.integrations.sources.semantic_scholar.time.sleep",
        lambda s: slept.append(s),
    )
    _provider(max_retries=1).search(query="x", limit=1)
    assert slept == [5.0]


def test_retry_after_invalid_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"n": 0}
    slept: list[float] = []
    body = json.dumps({"data": []}).encode()

    def _handler(req: object, timeout: float) -> _Resp:
        state["n"] += 1
        if state["n"] == 1:
            raise _http_error(429, retry_after="not-a-number")
        return _Resp(body)

    _install(monkeypatch, _handler)
    monkeypatch.setattr(
        "app.integrations.sources.semantic_scholar.time.sleep",
        lambda s: slept.append(s),
    )
    _provider(max_retries=1).search(query="x", limit=1)
    assert slept == [0.5]
