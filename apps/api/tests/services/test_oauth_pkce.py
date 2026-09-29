from app.services.oauth import make_pkce_verifier, pkce_challenge


def test_pkce_challenge_matches_rfc7636_s256_vector() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert (
        pkce_challenge(verifier)
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_pkce_verifier_is_url_safe_and_long_enough() -> None:
    verifier = make_pkce_verifier()
    assert len(verifier) >= 43
    assert "=" not in verifier
    assert all(
        char.isalnum() or char in "-_"
        for char in verifier
    )
