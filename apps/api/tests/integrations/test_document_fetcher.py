"""Fetcher tests: SSRF, redirects, size limits, content-type sniffing."""
from __future__ import annotations

import pytest

from app.integrations.documents.fetcher import (
    DocumentFetchFetcherError,
    DocumentTooLargeFetcherError,
    UnsafeUrlFetcherError,
    fetch_document,
)


class _FakeStream:
    def __init__(self, *, status_code=200, headers=None, body=b"") -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_bytes(self, chunk_size: int = 65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


def _patch_get(monkeypatch, responder):  # type: ignore[no-untyped-def]
    import app.integrations.documents.fetcher as mod
    monkeypatch.setattr(
        mod.httpx,
        "stream",
        lambda *a, **k: responder(),
    )


def test_unsafe_localhost_rejected() -> None:
    with pytest.raises(UnsafeUrlFetcherError):
        fetch_document(
            "http://127.0.0.1/secret",
            max_bytes=1024 * 1024,
            timeout_seconds=5,
            max_redirects=3,
        )


@pytest.mark.parametrize(
    "host",
    [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.0.1",
        "169.254.169.254",
        "0.0.0.0",
    ],
)
def test_private_and_special_ips_rejected(host: str) -> None:
    with pytest.raises(UnsafeUrlFetcherError):
        fetch_document(
            f"http://{host}/x",
            max_bytes=1024,
            timeout_seconds=5,
            max_redirects=3,
        )


def test_unsupported_scheme_rejected() -> None:
    with pytest.raises(UnsafeUrlFetcherError):
        fetch_document(
            "file:///etc/passwd",
            max_bytes=1024 * 1024,
            timeout_seconds=5,
            max_redirects=3,
        )


def test_body_too_large(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.integrations.documents.fetcher as mod
    monkeypatch.setattr(mod, "_assert_url_safe", lambda _url: None)
    _patch_get(
        monkeypatch,
        lambda: _FakeStream(
            status_code=200,
            headers={"content-type": "application/pdf"},
            body=b"x" * (1024 * 1024 + 1),
        ),
    )
    with pytest.raises(DocumentTooLargeFetcherError):
        fetch_document(
            "https://example.org/big.pdf",
            max_bytes=1024 * 1024,
            timeout_seconds=5,
            max_redirects=3,
        )


def test_body_at_max_bytes_succeeds(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.integrations.documents.fetcher as mod
    monkeypatch.setattr(mod, "_assert_url_safe", lambda _url: None)
    max_bytes = 1024
    _patch_get(
        monkeypatch,
        lambda: _FakeStream(
            status_code=200,
            headers={"content-type": "text/plain"},
            body=b"x" * max_bytes,
        ),
    )
    doc = fetch_document(
        "https://example.org/x",
        max_bytes=max_bytes,
        timeout_seconds=5,
        max_redirects=3,
    )
    assert doc.content_length == max_bytes


def test_http_404_raises(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.integrations.documents.fetcher as mod
    monkeypatch.setattr(mod, "_assert_url_safe", lambda _url: None)
    _patch_get(monkeypatch, lambda: _FakeStream(status_code=404))
    with pytest.raises(DocumentFetchFetcherError):
        fetch_document(
            "https://example.org/missing",
            max_bytes=1024 * 1024,
            timeout_seconds=5,
            max_redirects=3,
        )


def test_redirect_to_unsafe_rejected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.integrations.documents.fetcher as mod

    def _assert_safe(url: str) -> None:
        if "10.0.0.1" in url or "127.0.0.1" in url:
            raise UnsafeUrlFetcherError("unsafe")

    monkeypatch.setattr(mod, "_assert_url_safe", _assert_safe)

    _patch_get(
        monkeypatch,
        lambda: _FakeStream(
            status_code=302,
            headers={"location": "http://10.0.0.1/secret"},
        ),
    )
    with pytest.raises(UnsafeUrlFetcherError):
        fetch_document(
            "https://example.org/start",
            max_bytes=1024 * 1024,
            timeout_seconds=5,
            max_redirects=3,
        )


def test_pdf_magic_bytes_sniffing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.integrations.documents.fetcher as mod
    monkeypatch.setattr(mod, "_assert_url_safe", lambda _url: None)
    body = b"%PDF-1.4\n... header ..."
    _patch_get(
        monkeypatch,
        lambda: _FakeStream(
            status_code=200,
            headers={"content-type": "application/octet-stream"},
            body=body,
        ),
    )
    doc = fetch_document(
        "https://example.org/p",
        max_bytes=1024 * 1024,
        timeout_seconds=5,
        max_redirects=3,
    )
    assert doc.content_type == "application/pdf"
