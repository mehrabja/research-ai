"""Safe HTTP document fetcher.

Security model
--------------
* SSRF: hostname is resolved to IPs; each IP is checked against a
  deny list (private, loopback, link-local, multicast, reserved,
  unspecified). Every redirect target is validated the same way.

  Known limitation: DNS rebinding between resolution and connect is
  not mitigated. Full mitigation requires pinning the resolved IP
  into the HTTP transport (deferred).

* Body size: downloads are streamed and aborted once ``max_bytes`` is
  exceeded.

* Redirects: followed manually, one hop at a time, validating each
  target. Redirect loops and excess redirects are rejected.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = "research-ai-bot/0.1 (+extraction)"
_ALLOWED_SCHEMES = ("http", "https")
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_KNOWN_HEADERS = {
    "application/pdf",
    "text/html",
    "application/xhtml+xml",
    "text/plain",
}


class FetcherError(Exception):
    """Base for fetcher-level errors (mapped to AppError by callers)."""


class UnsafeUrlFetcherError(FetcherError):
    """SSRF guard rejected the URL."""


class DocumentTooLargeFetcherError(FetcherError):
    """Response body exceeds the configured limit."""


class DocumentFetchFetcherError(FetcherError):
    """Transport failure, non-2xx response, or redirect problem."""


@dataclass(frozen=True)
class FetchedDocument:
    url: str
    final_url: str
    content_type: str
    content_length: int
    content: bytes


def fetch_document(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    max_redirects: int,
) -> FetchedDocument:
    current = url
    for _ in range(max_redirects + 1):
        _assert_url_safe(current)
        try:
            with httpx.Client(
                timeout=timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": _USER_AGENT, "Accept": "*/*"},
            ) as client:
                with client.stream("GET", current) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise DocumentFetchFetcherError(
                            "redirect without Location header"
                        )
                    next_url = urljoin(current, location)
                    _assert_redirect_allowed(current, next_url)
                    current = next_url
                    continue

                if response.status_code >= 400:
                    raise DocumentFetchFetcherError(
                        f"HTTP {response.status_code}"
                    )

                advertised = response.headers.get("content-length")
                if advertised:
                    try:
                        if int(advertised) > max_bytes:
                            raise DocumentTooLargeFetcherError(
                                f"declared response body exceeded {max_bytes} bytes"
                            )
                    except ValueError:
                        pass
                body = _read_bounded(response, max_bytes)
                header_ct = _extract_header_content_type(response)
                final_ct = _sniff_content_type(header_ct, body, current)
                return FetchedDocument(
                    url=url,
                    final_url=current,
                    content_type=final_ct,
                    content_length=len(body),
                    content=body,
                )

        except httpx.TimeoutException as exc:
            raise DocumentFetchFetcherError("request timed out") from exc
        except httpx.HTTPError as exc:
            raise DocumentFetchFetcherError(
                f"transport error: {type(exc).__name__}"
            ) from exc

    raise DocumentFetchFetcherError("too many redirects")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _extract_header_content_type(response: httpx.Response) -> str:
    raw = response.headers.get("content-type", "")
    return raw.split(";", 1)[0].strip().lower()


def _read_bounded(response: httpx.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes(chunk_size=64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise DocumentTooLargeFetcherError(
                f"response body exceeded {max_bytes} bytes"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _sniff_content_type(header_ct: str, body: bytes, url: str) -> str:
    if body[:5] == b"%PDF-":
        return "application/pdf"
    if header_ct in _KNOWN_HEADERS:
        return header_ct
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return "application/pdf"
    if path.endswith(".html") or path.endswith(".htm"):
        return "text/html"
    if path.endswith(".txt"):
        return "text/plain"
    return header_ct or "application/octet-stream"


def _resolve_public_ips(host: str, port: int) -> set[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlFetcherError("could not resolve host") from exc

    ips: set[str] = set()
    for _family, _socktype, _proto, _canon, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            raise UnsafeUrlFetcherError("invalid resolved IP") from None
        if _is_unsafe_ip(ip):
            logger.warning("ssrf_blocked host=%s ip=%s", host, ip)
            raise UnsafeUrlFetcherError("resolved IP is not public")
        ips.add(ip.compressed)
    if not ips:
        raise UnsafeUrlFetcherError("host did not resolve to a public address")
    return ips


def _assert_url_safe(url: str) -> set[str]:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlFetcherError(f"unsupported scheme: {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise UnsafeUrlFetcherError("credentials in URL are not allowed")
    if parsed.fragment:
        raise UnsafeUrlFetcherError("URL fragments are not allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlFetcherError("missing host")
    port = parsed.port or _default_port(parsed.scheme)
    if port not in (80, 443):
        raise UnsafeUrlFetcherError("non-standard destination port is not allowed")
    first = _resolve_public_ips(host, port)
    second = _resolve_public_ips(host, port)
    if first != second:
        logger.warning("ssrf_dns_rebinding_detected host=%s", host)
        raise UnsafeUrlFetcherError("DNS resolution changed during validation")
    return first


def _assert_redirect_allowed(current: str, target: str) -> None:
    current_parsed = urlparse(current)
    target_parsed = urlparse(target)
    if target_parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlFetcherError("redirect target scheme is not allowed")
    if current_parsed.scheme == "https" and target_parsed.scheme != "https":
        raise UnsafeUrlFetcherError("HTTPS to HTTP downgrade is not allowed")
    _assert_url_safe(target)


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _is_unsafe_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


__all__ = [
    "DocumentFetchFetcherError",
    "DocumentTooLargeFetcherError",
    "FetchedDocument",
    "FetcherError",
    "UnsafeUrlFetcherError",
    "fetch_document",
]
