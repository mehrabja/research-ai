"""Trusted-proxy-aware client IP extraction (M36).

X-Forwarded-For is honoured ONLY when the direct peer belongs to a
configured trusted proxy network. Multiple XFF headers are concatenated
in header order before parsing.
"""
from __future__ import annotations

import ipaddress
import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache(maxsize=16)
def parse_trusted_proxies(raw: str) -> tuple[Network, ...]:
    out: list[Network] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            if "/" in token:
                out.append(ipaddress.ip_network(token, strict=False))
            else:
                addr = ipaddress.ip_address(token)
                out.append(
                    ipaddress.ip_network(
                        f"{addr}/{addr.max_prefixlen}", strict=False
                    )
                )
        except ValueError:
            logger.warning("invalid trusted proxy entry: %r", token)
    return tuple(out)


def _to_addr(raw: str):
    try:
        return ipaddress.ip_address(raw.strip())
    except ValueError:
        return None


def _is_trusted(addr, networks: tuple[Network, ...]) -> bool:
    return any(addr in net for net in networks)


def _scope_peer(scope: Mapping[str, Any]) -> str:
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and client:
        return str(client[0])
    return ""


def _all_xff(scope: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key, value in scope.get("headers") or []:
        if key == b"x-forwarded-for":
            try:
                parts.append(value.decode("latin-1"))
            except UnicodeDecodeError:
                continue
    return ",".join(parts)


def _normalize(raw: str) -> str | None:
    if not raw:
        return None
    addr = _to_addr(raw)
    if addr is None:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(addr)


def get_scope_client_ip(
    scope: Mapping[str, Any], *, trusted_proxies_raw: str
) -> str:
    """Resolve the client IP for rate limiting.

    Contract:

    * No trusted proxies configured:
        The direct peer address is used. X-Forwarded-For is ignored.

    * Direct peer is NOT in the trusted proxy set:
        X-Forwarded-For is ignored entirely. The peer is used.

    * Direct peer IS trusted:
        All X-Forwarded-For headers are concatenated in the order
        they were received, then split on commas.

        Valid entries are walked right-to-left:
          - The first valid entry that is NOT itself a trusted proxy
            address is the client.
          - If every valid entry is a trusted proxy address, the
            left-most valid entry is used.
          - If there are no valid entries, the direct peer is used.

        Malformed entries (non-IP strings) are skipped silently.

    IPv4-mapped IPv6 addresses are normalized to their IPv4 form.
    If the peer cannot be extracted at all, ``"unknown"`` is returned.
    """
    peer = _scope_peer(scope)
    networks = (
        parse_trusted_proxies(trusted_proxies_raw)
        if trusted_proxies_raw else ()
    )
    if not networks:
        return _normalize(peer) or "unknown"

    peer_addr = _to_addr(peer)
    if peer_addr is None or not _is_trusted(peer_addr, networks):
        return _normalize(peer) or "unknown"

    xff = _all_xff(scope)
    if not xff:
        return _normalize(peer) or "unknown"

    entries = [e.strip() for e in xff.split(",") if e.strip()]
    parsed = [(e, _to_addr(e)) for e in entries]
    valid = [(e, a) for e, a in parsed if a is not None]
    if not valid:
        return _normalize(peer) or "unknown"

    for entry, addr in reversed(valid):
        if not _is_trusted(addr, networks):
            return _normalize(entry) or "unknown"

    return _normalize(valid[0][0]) or "unknown"


__all__ = ["Network", "get_scope_client_ip", "parse_trusted_proxies"]
