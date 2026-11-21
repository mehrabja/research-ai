from __future__ import annotations

import io
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest

from app.integrations.sources.arxiv import ArxivProvider
from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderUnavailableError,
)

_ATOM = "http://www.w3.org/2005/Atom"
_ARXIV = "http://arxiv.org/schemas/atom"
_OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1/"


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _entry(
    *,
    arxiv_id: str = "2401.01234v2",
    title: str = "A transformer model",
    summary: str = "  A useful\n scientific   abstract. ",
    authors: tuple[str, ...] = ("Alice Example", "Bob Example"),
    published: str = "2024-01-03T00:00:00Z",
    doi: str | None = "10.1234/example",
) -> str:
    author_xml = "".join(
        f"<author><name>{name}</name></author>" for name in authors
    )
    doi_xml = f"<arxiv:doi>{doi}</arxiv:doi>" if doi else ""
    return (
        f"<entry><id>https://arxiv.org/abs/{arxiv_id}</id>"
        f"<title>{title}</title><summary>{summary}</summary>"
        f"{author_xml}<published>{published}</published>"
        f"{doi_xml}</entry>"
    )


def _feed(*entries: str, total: int | None = None) -> bytes:
    total_xml = (
        f'<opensearch:totalResults>{total}</opensearch:totalResults>'
        if total is not None
        else ""
    )
    xml = (
        f'<feed xmlns="{_ATOM}" xmlns:arxiv="{_ARXIV}" '
        f'xmlns:opensearch="{_OPENSEARCH}">{total_xml}'
        + "".join(entries)
        + "</feed>"
    )
    return xml.encode()


def _provider(*, retries: int = 0) -> ArxivProvider:
    return ArxivProvider(
        timeout_seconds=5,
        max_retries=retries,
        min_interval_seconds=0,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    handler,
) -> None:
    monkeypatch.setattr(
        "app.integrations.sources.arxiv.urllib.request.urlopen",
        handler,
    )


def test_search_maps_atom_entry_to_source_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(_feed(_entry(), total=1))

    _install(monkeypatch, handler)
    results = _provider().search(query="transformer", limit=25, year=2024)

    assert len(results) == 1
    candidate = results[0]
    assert candidate.source_api == "arxiv"
    assert candidate.external_source_id == "2401.01234"
    assert candidate.title == "A transformer model"
    assert candidate.abstract == "A useful scientific abstract."
    assert candidate.authors == ("Alice Example", "Bob Example")
    assert candidate.year == 2024
    assert candidate.doi == "10.1234/example"
    assert candidate.url == "https://arxiv.org/abs/2401.01234v2"

    url = requests[0].full_url  # type: ignore[attr-defined]
    params = parse_qs(urlparse(url).query)
    assert params["search_query"] == [
        "(all:transformer) AND (submittedDate:[202401010000 TO 202412312359])"
    ]
    assert params["max_results"] == ["25"]
    assert requests[0].get_header("User-agent") is not None  # type: ignore[attr-defined]


def test_search_caps_results_and_accepts_open_access_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []
    payload = _feed(_entry(), total=1)

    def handler(request: object, timeout: float) -> _Response:
        requests.append(request)
        return _Response(payload)

    _install(monkeypatch, handler)
    results = _provider().search(
        query="neural networks", limit=250, open_access_only=True
    )

    assert len(results) == 1
    params = parse_qs(urlparse(requests[0].full_url).query)  # type: ignore[attr-defined]
    assert params["max_results"] == ["100"]


@pytest.mark.parametrize(
    ("raw_id", "expected"),
    [
        ("2401.01234v3", "2401.01234"),
        ("hep-th/9901001v2", "hep-th/9901001"),
    ],
)
def test_old_and_new_ids_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
    raw_id: str,
    expected: str,
) -> None:
    _install(
        monkeypatch,
        lambda request, timeout: _Response(
            _feed(_entry(arxiv_id=raw_id))
        ),
    )
    result = _provider().search(query="test", limit=1)
    assert result[0].external_source_id == expected


def test_arxiv_http_200_error_feed_is_not_treated_as_a_paper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = (
        f'<feed xmlns="{_ATOM}"><entry>'
        "<id>http://arxiv.org/api/errors#bad_query</id>"
        "<summary>Invalid search query</summary>"
        "</entry></feed>"
    )
    _install(
        monkeypatch,
        lambda request, timeout: _Response(error.encode()),
    )
    with pytest.raises(SourceProviderInvalidResponseError, match="Invalid search query"):
        _provider().search(query="bad", limit=1)


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
    exc = urllib.error.HTTPError(
        "https://export.arxiv.org/api/query",
        status,
        "HTTP error",
        {},
        io.BytesIO(b""),
    )
    _install(
        monkeypatch,
        lambda request, timeout: (_ for _ in ()).throw(exc),
    )
    with pytest.raises(error_type):
        _provider().search(query="test", limit=1)


def test_invalid_xml_and_dtd_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, lambda request, timeout: _Response(b"not-xml"))
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="test", limit=1)

    _install(
        monkeypatch,
        lambda request, timeout: _Response(
            b'<!DOCTYPE feed [<!ENTITY x "expansion">]><feed/>'
        ),
    )
    with pytest.raises(SourceProviderInvalidResponseError, match="DTD"):
        _provider().search(query="test", limit=1)


def test_empty_query_and_invalid_year_are_rejected() -> None:
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query=" ", limit=1)
    with pytest.raises(SourceProviderInvalidResponseError):
        _provider().search(query="test", limit=1, year=True)
