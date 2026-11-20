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


def test_authorization_url_uses_local_callback_when_redirect_is_unset(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.services.oauth import authorization_url

    settings = get_settings()
    monkeypatch.setattr(settings, "google_oauth_client_id", "test-google-client")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "test-google-secret")
    monkeypatch.setattr(settings, "google_oauth_redirect_uri", "")
    monkeypatch.setattr(settings, "web_app_base_url", "http://localhost:3000")

    url = authorization_url("google", "google.test-state", "test-challenge")
    assert "client_id=test-google-client" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Foauth%2Fgoogle%2Fcallback" in url
    assert "code_challenge_method=S256" in url


def test_authorization_url_rejects_missing_provider_credentials(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.core.exceptions import OAuthProviderNotConfigured
    from app.services.oauth import authorization_url

    settings = get_settings()
    monkeypatch.setattr(settings, "github_oauth_client_id", "")
    monkeypatch.setattr(settings, "github_oauth_client_secret", "")

    try:
        authorization_url("github", "github.test-state", "test-challenge")
    except OAuthProviderNotConfigured:
        return
    raise AssertionError("missing provider credentials must be rejected")
