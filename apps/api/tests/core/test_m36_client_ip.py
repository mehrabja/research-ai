from __future__ import annotations

from app.core.client_ip import get_scope_client_ip


def _scope(peer, headers=None) -> dict:
    return {"type": "http", "client": peer, "headers": headers or []}


def test_direct_peer_no_trusted() -> None:
    assert get_scope_client_ip(
        _scope(("1.2.3.4", 0)), trusted_proxies_raw=""
    ) == "1.2.3.4"


def test_untrusted_peer_ignores_xff() -> None:
    s = _scope(("5.6.7.8", 0), [(b"x-forwarded-for", b"1.2.3.4")])
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "5.6.7.8"


def test_ipv4_mapped_ipv6_normalized() -> None:
    s = _scope(("::ffff:1.2.3.4", 0))
    assert get_scope_client_ip(s, trusted_proxies_raw="") == "1.2.3.4"


def test_missing_peer_returns_unknown() -> None:
    assert get_scope_client_ip(
        _scope(None), trusted_proxies_raw=""
    ) == "unknown"


def test_trusted_peer_single_xff() -> None:
    s = _scope(("10.0.0.1", 0), [(b"x-forwarded-for", b"1.2.3.4")])
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "1.2.3.4"


def test_trusted_peer_multi_hop() -> None:
    s = _scope(
        ("10.0.0.1", 0),
        [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.2, 10.0.0.3")],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "1.2.3.4"


def test_all_xff_trusted_returns_leftmost() -> None:
    s = _scope(
        ("10.0.0.1", 0),
        [(b"x-forwarded-for", b"10.0.0.5, 10.0.0.6")],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "10.0.0.5"


def test_trusted_peer_no_xff() -> None:
    s = _scope(("10.0.0.1", 0))
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "10.0.0.1"


def test_malformed_xff_entry_skipped() -> None:
    s = _scope(
        ("10.0.0.1", 0),
        [(b"x-forwarded-for", b"not-an-ip, 1.2.3.4")],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "1.2.3.4"


def test_all_malformed_xff_falls_back() -> None:
    s = _scope(("10.0.0.1", 0), [(b"x-forwarded-for", b"garbage")])
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "10.0.0.1"


def test_multiple_xff_headers_concatenated_in_order() -> None:
    s = _scope(
        ("10.0.0.1", 0),
        [
            (b"x-forwarded-for", b"1.2.3.4"),
            (b"x-forwarded-for", b"10.0.0.2, 10.0.0.3"),
        ],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "1.2.3.4"


def test_multiple_xff_untrusted_peer_ignored() -> None:
    s = _scope(
        ("5.6.7.8", 0),
        [
            (b"x-forwarded-for", b"1.2.3.4"),
            (b"x-forwarded-for", b"2.3.4.5"),
        ],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "5.6.7.8"


def test_multiple_xff_mixed_valid_invalid() -> None:
    s = _scope(
        ("10.0.0.1", 0),
        [
            (b"x-forwarded-for", b"1.2.3.4"),
            (b"x-forwarded-for", b"not-an-ip"),
            (b"x-forwarded-for", b"10.0.0.2"),
        ],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "1.2.3.4"


def test_multiple_xff_all_trusted_leftmost() -> None:
    s = _scope(
        ("10.0.0.1", 0),
        [
            (b"x-forwarded-for", b"10.0.0.10"),
            (b"x-forwarded-for", b"10.0.0.11"),
        ],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "10.0.0.10"


def test_multiple_xff_all_invalid_falls_back() -> None:
    s = _scope(
        ("10.0.0.1", 0),
        [
            (b"x-forwarded-for", b"garbage"),
            (b"x-forwarded-for", b"also-garbage"),
        ],
    )
    assert get_scope_client_ip(
        s, trusted_proxies_raw="10.0.0.0/8"
    ) == "10.0.0.1"


def test_invalid_trusted_proxy_config_ignored() -> None:
    s = _scope(("9.9.9.9", 0), [(b"x-forwarded-for", b"1.2.3.4")])
    assert get_scope_client_ip(
        s, trusted_proxies_raw="not-a-cidr"
    ) == "9.9.9.9"
